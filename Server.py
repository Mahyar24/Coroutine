import socket

from pyos import *

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(("localhost", 12345))
sock.listen()
sock.setblocking(False)


def handle_client(client, address):
    while True:
        yield SystemCallRequest(SystemCall.wait_io_read, io=client)
        data = client.recv(1024)
        if not data:
            break
        try:
            pass
            # print(data.decode('utf-8'), end='')
        except UnicodeError:
            break
        yield SystemCallRequest(SystemCall.wait_io_write, io=client)
        client.send(b'Server Got Your Message: "' + data[:-1] + b'".\n')
    yield SystemCallRequest(SystemCall.wait_io_write, io=client)
    client.close()
    print(f"{address} closed")


def server():
    print("Server starting")
    while True:
        yield SystemCallRequest(SystemCall.wait_io_read, io=sock)
        client, address = sock.accept()
        yield SystemCallRequest(
            SystemCall.new, func=handle_client, args=(client, address)
        )


scheduler = Scheduler(sleep=0.001)
scheduler.new(server)
scheduler.MainLoop()
