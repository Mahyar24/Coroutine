#! /usr/bin/python3.9

"""
This is an example for using `PyOs` module.
look at that file docstrings for more information.
Mahyar@Mahyar24.com, Sat 19 Oct 2019.
"""

import socket

from PyOS import Scheduler, SystemCall, SystemCallRequest

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(("localhost", 12345))
sock.listen()
sock.setblocking(False)


def handle_client(client, address):
    """
    Printing incoming data and send it back.
    """
    while True:
        yield SystemCallRequest(SystemCall.WAIT_IO_READ, io=client)
        data = client.recv(1024)
        if not data:
            break
        try:
            handle_client_id = yield SystemCallRequest(SystemCall.ID)
            print(
                f"Incoming data from {address!r} with ID of {handle_client_id!r}:"
                f'\n---> {data.decode("utf-8").strip()!r}.'
            )
        except UnicodeError:
            break
        yield SystemCallRequest(SystemCall.WAIT_IO_WRITE, io=client)
        client.send(b'Server Got Your Message: "' + data.strip() + b'".\n')
    yield SystemCallRequest(SystemCall.WAIT_IO_WRITE, io=client)
    client.close()
    print(f"{address!r} closed.")


def server():
    """
    Starting the sever and accept socket connections.
    """
    sever_id = yield SystemCallRequest(SystemCall.ID)
    print(f"Server started with ID of {sever_id!r}")
    while True:
        yield SystemCallRequest(SystemCall.WAIT_IO_READ, io=sock)
        client, address = sock.accept()
        print(f"{address!r} connected.")
        new_task_id = yield SystemCallRequest(
            SystemCall.NEW, func=handle_client, args=(client, address)
        )
        print(f"Creating a task for incoming client with ID of {new_task_id!r}")


if __name__ == "__main__":
    scheduler = Scheduler(sleep=0.001, run_for_ever=True)
    scheduler.new(server)
    scheduler.run()
