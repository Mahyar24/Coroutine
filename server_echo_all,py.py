#! /usr/bin/python3.9

"""
This is an example for using `PyOs` module.
look at that file docstrings for more information.
Mahyar@Mahyar24.com, Sat 19 Oct 2019.
"""

import queue
import socket

from PyOS import Scheduler, SystemCall, SystemCallRequest

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(("0.0.0.0", 12345))
sock.listen()
sock.setblocking(False)

CLIENTS = []


def echo_to_all_clients(message_queue):
    """
    Sending the message to every clients except the sender himself!
    All coroutines must have at least one yield statement that we are
    sure it gets run, otherwise it will stock in queue and never ends.
    So in cases like here that we are not certain are main yield statement
    will run, we must fake a yield; e.g. a SystemCall.ID.
    (If there is no peer except sender, we need last yield statement.)
    """
    sender, message = message_queue.get()
    for client in CLIENTS:
        if client != sender:
            yield SystemCallRequest(SystemCall.WAIT_IO_WRITE, io=client)
            try:
                client.send(
                    bytes(
                        f"Peer {sender.fileno()!r}: {message.decode('utf-8')!r}\n",
                        "utf-8",
                    )
                )  # .filno() != id.
            except (BrokenPipeError, OSError):
                pass

    yield SystemCallRequest(SystemCall.ID)  # Look at docstring!


def close_client(client, message_queue, address):
    """
    Closing the connection and saying that to all remaining clients.
    """
    message_queue.put((client, b"CLOSED!"))  # Making it a message to broadcast!
    closing_id = yield SystemCallRequest(
        SystemCall.NEW, func=echo_to_all_clients, args=(message_queue,)
    )

    yield SystemCallRequest(
        SystemCall.WAIT, id_=closing_id
    )  # Wait for telling everybody that the peer is closed, then terminate it.
    # (so nobody see a message with fileno -1)
    yield SystemCallRequest(SystemCall.WAIT_IO_WRITE, io=client)
    client.close()
    CLIENTS.remove(client)
    print(f"{address!r} closed.")


def handle_client(client, address, message_queue):
    """
    Printing incoming data and send it back.
    """
    handle_client_id = yield SystemCallRequest(SystemCall.ID)

    while True:
        yield SystemCallRequest(SystemCall.WAIT_IO_READ, io=client)  # Waiting for data
        data = client.recv(1024)
        if not data:
            break  # if no data, break and terminate
        try:
            data = data.strip()
            print(
                f"Incoming data from {address!r} with ID of {handle_client_id!r}:"
                f'\n---> {data.decode("utf-8")!r}.'
            )
        except UnicodeError:
            break
        else:
            message_queue.put(
                (
                    client,
                    data,
                )
            )
            yield SystemCallRequest(
                SystemCall.NEW, func=echo_to_all_clients, args=(message_queue,)
            )  # Echo back the message to everybody else!

            yield SystemCallRequest(SystemCall.WAIT_IO_WRITE, io=client)  # Send Ack!
            client.send(b'Ack: "' + data + b'".\n')

    closing_id = yield SystemCallRequest(  # Making a coroutine to get closed.
        SystemCall.NEW,
        func=close_client,
        args=(client, message_queue, address),
    )
    yield SystemCallRequest(
        SystemCall.WAIT, id_=closing_id
    )  # waiting for connection to terminate.
    print(f"My existence ({handle_client_id!r}) reached the end; Bye you all!")


def server():
    """
    Starting the sever and accept socket connections.
    """
    sever_id = yield SystemCallRequest(SystemCall.ID)
    print(f"Server started with ID of {sever_id!r}")

    messages = queue.Queue()

    while True:
        yield SystemCallRequest(SystemCall.WAIT_IO_READ, io=sock)
        client, address = sock.accept()
        print(f"{address!r} connected.")
        CLIENTS.append(client)

        new_task_id = yield SystemCallRequest(
            SystemCall.NEW, func=handle_client, args=(client, address, messages)
        )
        print(f"Creating a task for incoming client with ID of {new_task_id!r}")


if __name__ == "__main__":
    scheduler = Scheduler(interval=1e-5, run_for_ever=True)
    scheduler.new(server)
    scheduler.run()
