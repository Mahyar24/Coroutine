#! /usr/bin/python3.9

"""
This is an example for using `PyOs` module.
look at that file docstrings for more information.
Mahyar@Mahyar24.com, Sat 19 Oct 2019.
"""

from PyOS import Scheduler, SystemCall, SystemCallRequest


def print_odd():
    num = 1
    while True:
        print(f"Odd:--------> {num}")
        num += 2
        yield SystemCallRequest(SystemCall.SLEEP, sleep_time=1.0)


def print_even():
    num = 2
    while True:
        print(f"Even:---> {num}")
        num += 2
        yield SystemCallRequest(SystemCall.SLEEP, sleep_time=5.0)


def print_numbers():
    id_ = yield SystemCallRequest(SystemCall.ID)
    print(f"Printing numbers started with ID of {id_!r}")
    odd = yield SystemCallRequest(SystemCall.NEW, func=print_odd)
    even = yield SystemCallRequest(SystemCall.NEW, func=print_even)

    yield SystemCallRequest(
        SystemCall.SLEEP, sleep_time=60.0
    )  # killing both tasks after 60.0s
    yield SystemCallRequest(SystemCall.KILL, id_=odd)
    yield SystemCallRequest(SystemCall.KILL, id_=even)


def main():
    """
    We should print odd numbers up to 119 because we have 60s before termination
    -> 60 * 2 = 120. But if we have a large interval like here (0.1s) we get much less
    final number. The reason is that we are sleeping a lot in our scheduler; but if we don't
    cpu usage will increase rapidly.
    P.S: It's only a PoC!
    """
    scheduler = Scheduler(interval=0.1, run_for_ever=False)
    scheduler.new(print_numbers)
    scheduler.run()


if __name__ == "__main__":
    main()
