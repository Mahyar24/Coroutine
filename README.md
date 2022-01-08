# Intro

This code is a Proof of Concept for having a grasp of how event loops works under the hood.
The main inspiration is from David Beazley talk (http://dabeaz.com).
Link to the talk: https://youtu.be/Y4Gt3Xjd7G8. It's awesome.
It's worth to mention that all of the magic is happening by the select library.
Read the docs about it. https://docs.python.org/3/library/select.html

This code must NOT used for production.
Look at the 'server_example.py' and other files for watching this module in use.

Compatible with python3.9+. No third-party library is required, implemented in pure python.

This piece of code is a POC, (but a powerful minimalistic one!)
so it's not gonna follow community (PEP) and pylint principals/recommendations strictly.


## API
```
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
```

## Contributing
Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

Contact me: <OSS@Mahyar24.com> :)

## License
[GNU GPLv3 ](https://choosealicense.com/licenses/gpl-3.0/)
