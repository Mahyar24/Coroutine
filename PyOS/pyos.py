#! /usr/bin/python3.9

"""
This code is a Proof of Concept for having a grasp of how event loops works under the hood.
The main inspiration is from David Beazley talk (http://dabeaz.com).
Link to the talk: https://youtu.be/Y4Gt3Xjd7G8. It's awesome.
It's worth to mention that all of the magic is happening by the select library.
Read the docs about it. https://docs.python.org/3/library/select.html
this code must NOT used for production.
Look at the 'server_example.py' and other files for watching this module in use.
Compatible with python3.9+. No third-party library is required, implemented in pure python.
* This piece of code is a POC, (but a powerful minimalistic one!)
so it's not gonna follow community (PEP) and pylint principals/recommendations strictly. *
Mahyar@Mahyar24.com, Sat 19 Oct 2019.
"""

from __future__ import annotations

import enum
import queue
import select
import time
from collections import defaultdict
from typing import Any, Callable, DefaultDict, Generator, Optional, Union

__all__ = ["SystemCall", "SystemCallRequest", "Scheduler"]


class SystemCall(enum.Enum):
    """
    For ease of use in `SystemCallRequest` class. this enum indicate your type of requests.
    """

    ID = 1  # SystemCall for getting the unique id of the task.
    SLEEP = 2  # SystemCall for non blocking sleep.
    NEW = 3  # SystemCall for making a new task.
    KILL = 4  # SystemCall for killing the task.
    WAIT = 5  # SystemCall for wait for some task to finish.
    WAIT_IO_READ = 6  # SystemCall for waiting to read IO. (notified by OS Select)
    WAIT_IO_WRITE = 7  # SystemCall for waiting to write IO. (notified by OS Select)


class SystemCallRequest:  # pylint: disable=R0903
    """
    This class make an approach for talking to the scheduler. When you want to wait for a task
    or do some IOs you can yield a `SystemCallRequest` with the required args and kwargs; then
    when scheduler find out, it will call the SystemCallRequest.handle method to deal with it.
    The API:
        When you want to do something that gonna waste some cpu cycles waiting for no good,
        you should yield a SystemCallRequest first with appropriate inputs and in the next line
        do those tasks. If it's expected that request would return an answer you can assign
        the SystemCallRequest yield to a value. Look at ../server_example.py for a sample.py
        Here are some general SystemCallRequests:

        id = yield SystemCallRequest(SystemCall.ID) -> get id of present task in the scheduler.py
        sleep_id = yield SystemCallRequest(SystemCall.SLEEP, sleep_time=10.0) ->
                    Non blocking sleep for 10.0 second while event loop does others thing.
                    You should be aware of that it's not really accurate and you should
                    lower Scheduler sleep time for better accuracy.
        new_func_id = yield SystemCallRequest(
                    SystemCall.NEW, func=new_func, args=(..., ), kwargs={}
                        ) -> making a new task and put it in scheduler.
        exception = yield SystemCallRequest(
                    SystemCall.KILL, id_=task_to_kill.id
                        ) -> kill a task; for security reasons which are obvious you
                        cannot kill tasks that are created earlier and if you do so,
                        you will get a PermissionError exception as return value.
        exception = yield SystemCallRequest(
                    SystemCall.WAIT, id_=task_to_wait.id
                        ) -> wait for a task to complete; for security reasons which are obvious you
                        cannot wait for tasks that are created earlier and if you do so,
                        you will get a PermissionError exception as return value.
        yield SystemCallRequest(
                    SystemCall.WAIT_IO_READ, io=some_socket_waiting_to_read
                        ) -> wait for IO read. (same for IO write) It's mandatory that you will pass
                        the run_for_ever argument value to be True in the scheduler .run() method,
                        unless program will crash and it will raise a ValueError.
    """

    def __init__(  # pylint: disable=R0913
        self,
        request: SystemCall,
        func: Optional[
            Callable[..., Generator[Optional[SystemCallRequest], Any, Any]]
        ] = None,
        id_: Optional[int] = None,  # When you want to kill some task or wait for them.
        sleep_time: Optional[float] = None,
        io: Optional[Any] = None,
        args: Optional[tuple[Any, ...]] = None,
        kwargs: Optional[dict[str, Any]] = None,
    ) -> None:
        self.request = request
        self.func = func
        self.io = io  # pylint: disable=C0103
        self.id = id_  # pylint: disable=C0103
        self.sleep_time = sleep_time
        self.args = args
        self.kwargs = kwargs

    def handle(self, task: Task, sch: Scheduler) -> None:  # pylint: disable=R0912
        """
        Based on your request (SystemCall) this method will handle the demands.
        """
        if self.request == SystemCall.ID:
            task.val = task.id
        if self.request == SystemCall.SLEEP:
            if self.sleep_time is not None:
                task.val = sch.sleep(task.id, self.sleep_time)
                sch.waiting[task.id].add(task.val)
        elif self.request == SystemCall.NEW:
            if self.func is not None:
                sub_id = sch.new(self.func, self.args, self.kwargs)
                task.val = sub_id
            else:
                raise ValueError("you should specify func!")
        elif self.request == SystemCall.KILL:
            if self.id is not None:
                if (
                    self.id > task.id and self.id != sch.io_id
                ):  # Check that latter tasks cannot kill earlier ones.
                    sch.tasks[self.id].task.close()
                else:
                    task.val = PermissionError(
                        f"You cannot kill task with id number of: {self.id!r}"
                    )
            else:
                raise ValueError("you should specify id_")
        elif self.request == SystemCall.WAIT:
            if self.id is not None:
                if (
                    self.id > task.id and self.id != sch.io_id
                ):  # Check that latter tasks cannot wait on earlier ones.
                    sch.waiting[task.id].add(self.id)
                else:
                    task.val = PermissionError(
                        f"You cannot wait task with id number of: {self.id!r}"
                    )
            else:
                raise ValueError("you should specify id_")
        elif self.request == SystemCall.WAIT_IO_READ:
            if self.io is not None:
                if sch.run_for_ever:
                    sch.read_waiting[self.io].add(task)
                    sch.waiting[task.id].add(sch.io_id)
                else:
                    raise ValueError(
                        "if you want to wait for IO, scheduler 'run_for_ever' must be True."
                    )
            else:
                raise ValueError("you should specify io")
        elif self.request == SystemCall.WAIT_IO_WRITE:
            if self.io is not None:
                if sch.run_for_ever:
                    sch.write_waiting[self.io].add(task)
                    sch.waiting[task.id].add(sch.io_id)
                else:
                    raise ValueError(
                        "if you want to wait for IO, scheduler 'run_for_ever' must be True."
                    )
            else:
                raise ValueError("you should specify io")


class Task:  # pylint: disable=R0903
    """
    Task objects are a wrapper for tasks inside the scheduler (event loop).
    It is used internally by scheduler for smoothing the procedure.
    We can imagine this method to be synonym of asyncio.create_task function.
    """

    Nums: int = 0

    def __init__(
        self,
        task: Callable[..., Generator[Optional[SystemCallRequest], Any, Any]],
        args: Optional[tuple[Any, ...]] = None,
        kwargs: Optional[dict[str, Any]] = None,
    ) -> None:
        Task.Nums += 1
        if args is not None:
            if kwargs is not None:
                self.task = task(*args, **kwargs)
            else:
                self.task = task(*args)
        else:
            if kwargs is not None:
                self.task = task(**kwargs)
            else:
                self.task = task()
        self.val: Any = None
        self.id = Task.Nums  # pylint: disable=C0103

    def run(self) -> Union[SystemCallRequest, Any]:
        """
        make the task initialized or continue by getting benefit of sending value to generator.
        """
        return self.task.send(self.val)


class Scheduler:  # pylint: disable=R0902
    """
    This is the scheduler class that is equivalent of asyncio BaseEventLoop.
    Formal use of this class is to make a scheduler and pass your main function to it by
    Scheduler.new method, and begin the work by Scheduler.run().
    When there is a blocking IO, you should give back the control to
    the scheduler to work on other tasks.
    If there is waiting on IOs, scheduler must listen for IO unlimitedly so run_for_ever
    option must be True, otherwise module will raise an error.
    Therefore, it will handle the tasks concurrently for you.
    """

    def __init__(self, interval: float = 0.01, run_for_ever: bool = True) -> None:
        self.queue: queue.Queue = queue.Queue()
        self.tasks: dict[int, Task] = {}
        self.waiting: DefaultDict[int, set[int]] = defaultdict(
            set
        )  # Waiting for another coroutine; {1: 2} -> task 1 is waiting for task 2 to complete
        self.read_waiting: DefaultDict[int, set[Task]] = defaultdict(
            set
        )  # waiting for some blocking reading IO
        self.write_waiting: DefaultDict[int, set[Task]] = defaultdict(
            set
        )  # waiting for some blocking reading IO
        self.sleep_waiting: dict[int, float] = {}
        self.io_id: int = 0
        self.interval: float = interval
        self.run_for_ever = run_for_ever

    def new(
        self,
        operation: Callable[..., Generator[Optional[SystemCallRequest], Any, Any]],
        args: Optional[tuple[Any, ...]] = None,
        kwargs: Optional[dict[str, Any]] = None,
    ) -> int:
        """
        You should pass your main function to the scheduler by using this method.
        Something like this: Scheduler().new(main). If you want to create a new task and add them
        to scheduler, do NOT use this method (except for main) instead make SystemCallRequest: ->
        yield SystemCallRequest(SystemCall.NEW, func=<SomeFunc>, args=(<x>, <y>))
        """
        task = Task(operation, args, kwargs)
        self.tasks[task.id] = task
        self.schedule(task)
        return task.id

    def schedule(self, task: Task) -> None:
        """
        Used internally for adding tasks to the scheduler.
        Equivalent of asyncio loop.call_soon
        """
        self.queue.put(task)

    def kill_task_id(self, task_id: int) -> None:
        """
        Used internally for `kill` method.
        """
        self.waiting.pop(task_id, None)
        self.read_waiting.pop(task_id, None)
        self.write_waiting.pop(task_id, None)

        for key in self.waiting:  # remove this task in any wait task queue
            self.waiting[key].discard(task_id)

        for i in self.read_waiting, self.write_waiting:
            for key in i:
                i[key].discard(self.tasks[task_id])

        del self.tasks[task_id]

    def kill(self, item: Task) -> None:
        """
        Used internally for killing tasks and pulling them out of scheduler.
        Equivalent of cancelling in asyncio.
        """

        for key, value in self.tasks.copy().items():
            if value == item:
                self.kill_task_id(key)
                break

    def io_checking(
        self, timeout: Optional[float]
    ) -> None:  # TODO: use select.epoll instead of select.select.
        """
        Here is all the magic happens. The OS somehow make a notification for us that some IOs
        are ready, and if that occurred the scheduler will context switch to that matter.
        """
        if self.read_waiting or self.write_waiting:
            read_ios, write_ios, _ = select.select(
                self.read_waiting.keys(), self.write_waiting.keys(), (), timeout
            )
            for read_io in read_ios:
                for i in self.read_waiting[read_io]:
                    self.waiting[i.id].discard(self.io_id)
                    self.schedule(i)
                del self.read_waiting[read_io]
            for write_io in write_ios:
                for i in self.write_waiting[write_io]:
                    self.waiting[i.id].discard(self.io_id)
                    self.schedule(i)
                del self.write_waiting[write_io]

    def io(self) -> Generator[None, Any, None]:  # pylint: disable=C0103
        """
        If you pass tha `forever=True` in Scheduler.run method, this function will add to scheduler
        and it will look for ready IOs constantly.
        """
        while True:
            if self.queue.empty():
                self.io_checking(None)
            else:
                self.io_checking(0)
            yield

    def _sleep(self, task_id: int, sleeping_time: float) -> Generator[None, None, None]:
        """
        Internal mechanism used in .sleep method for non blocking sleeping.
        Checking in every iteration for if the wait is over or not
        (so yielding back again).
        """
        self.sleep_waiting[task_id] = time.time()
        while True:
            if (time.time() - self.sleep_waiting[task_id]) > sleeping_time:
                del self.sleep_waiting[task_id]
                break
            yield

    def sleep(self, task_id: int, sleeping_time: float) -> int:
        """
        Making a new task to yield every time unless we wait enough.
        """
        return self.new(self._sleep, (task_id, sleeping_time))

    def should_not_wait(self, item: Task) -> bool:
        """
        Determining that we should wait (based on queue item) or we should run.
        """
        if self.waiting:
            if all(
                (v == set() for v in self.waiting.values())
            ):  # if all ot the values were empty sets we shouldn't wait
                return True
            if item.id not in self.waiting.keys() or not self.waiting[item.id]:
                return True
            return False
        return True

    def run(self) -> None:
        """
        The main loop begins and exist in here. This method will iterate over the tasks and
        make them work concurrently. There is a sleep implementation for not using 100% of CPU but
        if there is a demand for speed or you are working with lots of simultaneously IOs,
        you can lower the sleep time or make it 0.
        """
        if self.run_for_ever:
            self.io_id = self.new(self.io)
        while self.tasks:
            item = self.queue.get()
            # print(
            #     f"Working on {item.id!r}. Waiting: {dict(self.waiting)}."
            # )  # Increase sleep time and watch the context switching.
            if self.should_not_wait(item):
                try:
                    result = item.run()
                except StopIteration:
                    self.kill(item)
                else:
                    if isinstance(result, SystemCallRequest):
                        result.handle(item, self)
                    self.schedule(item)
            else:
                self.schedule(item)
                time.sleep(self.interval)
