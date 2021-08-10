import enum
import queue
import select
import time

__all__ = ("SystemCall", "SystemCallRequest", "Task", "Scheduler")


class SystemCall(enum.Enum):
    id_ = 1
    new = 2
    kill = 3
    wait = 4
    wait_io_read = 5
    wait_io_write = 6


class SystemCallRequest:
    def __init__(self, request, func=None, id_=None, io=None, args=None, kwargs=None):
        self.request = request
        self.func = func
        self.io = io
        self.id = id_
        self.args = args
        self.kwargs = kwargs

    def handle(self, task, sch):
        if self.request == SystemCall.id_:
            task.val = task.id
        elif self.request == SystemCall.new:
            sub_id = sch.new(self.func, self.args, self.kwargs)
            task.val = sub_id
        elif self.request == SystemCall.kill:
            sch.tasks[self.id].task.close()
        elif self.request == SystemCall.wait:
            sch.waiting[task.id] = self.id
        elif self.request == SystemCall.wait_io_read:
            sch.read_waiting[self.io] = task
            sch.waiting[task.id] = sch.io_id
        elif self.request == SystemCall.wait_io_write:
            sch.write_waiting[self.io] = task
            sch.waiting[task.id] = sch.io_id


class Task:
    Nums = 0

    def __init__(self, task, args=None, kwargs=None):
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
        self.val = None
        self.id = Task.Nums

    def run(self):
        return self.task.send(self.val)


class Scheduler:
    def __init__(self, sleep=0.01):
        self.queue = queue.Queue()
        self.tasks = {}
        self.waiting = (
            {}
        )  # Waiting for another coroutine; {1: 2} -> task 1 is waiting for task 2 to complete
        self.read_waiting = {}  # waiting for some blocking reading IO
        self.write_waiting = {}  # waiting for some blocking reading IO
        self.io_id = None
        self.sleep = sleep

    def new(self, operation, args=None, kwargs=None):
        task = Task(operation, args, kwargs)
        self.tasks[task.id] = task
        self.schedule(task)
        return task.id

    def schedule(self, task):
        self.queue.put(task)

    def kill(self, task_id):
        for waiting, waiting_for in self.waiting.copy().items():
            if waiting_for == task_id:
                del self.waiting[waiting]
        del self.tasks[task_id]

    def io_checking(self, timeout):
        if self.read_waiting or self.write_waiting:
            read_ios, write_ios, _ = select.select(
                self.read_waiting.keys(), self.write_waiting.keys(), (), timeout
            )
            for read_io in read_ios:
                del self.waiting[self.read_waiting[read_io].id]
                self.schedule(self.read_waiting.pop(read_io))
            for write_io in write_ios:
                del self.waiting[self.write_waiting[write_io].id]
                self.schedule(self.write_waiting.pop(write_io))

    def io(self):
        while True:
            if self.queue.empty():
                self.io_checking(None)
            else:
                self.io_checking(0)
            yield

    def MainLoop(self, forever=True):
        if forever:
            self.io_id = self.new(self.io)
        while self.tasks:
            item = self.queue.get()
            if not self.waiting or item.id not in self.waiting.keys():
                try:
                    result = item.run()
                except StopIteration:
                    try:
                        self.kill(
                            *[
                                task_id
                                for task_id in self.tasks
                                if self.tasks[task_id] == item
                            ]
                        )
                    except TypeError:
                        pass
                else:
                    if isinstance(result, SystemCallRequest):
                        result.handle(item, self)
                    self.schedule(item)
            else:
                self.schedule(item)
            time.sleep(self.sleep)


if __name__ == "__main__":

    def main():
        while True:
            print("Alive")
            time.sleep(0.001)
            yield

    scheduler = Scheduler()
    scheduler.new(main)
    scheduler.MainLoop(forever=True)
