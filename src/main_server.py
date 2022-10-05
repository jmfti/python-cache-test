import socketserver
from gc import collect
from typing import Optional, List
from pymongo import errors
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, EmailStr
from pydantic import Field
import logging, logging.config
import asyncio
from starlette_prometheus import metrics, PrometheusMiddleware
# from metrics.scheduled_tasks import collect_metrics
import random, os
from prometheus_client import start_http_server
from threading import Thread

app = FastAPI()
app.add_middleware(PrometheusMiddleware)

@app.on_event("startup")
async def prepare_things():
    env = dict(os.environ)
    try:
        t = Thread(target=start_http_server, args=(8000))
        t2 = Thread(target=start_udp_server)
        t.start()
        t2.start()
    except OSError as e:
        # it just means a worker already opened the server, so pass through
        pass
    

def start_udp_server():
    HOST, PORT = "localhost", 9999
    with socketserver.UDPServer((HOST, PORT), MyUDPHandler) as server:
        server.serve_forever()


class MyUDPHandler(socketserver.BaseRequestHandler):
    """
    This class works similar to the TCP handler class, except that
    self.request consists of a pair of data and client socket, and since
    there is no connection the client address must be given explicitly
    when sending data back via sendto().
    """

    def handle(self):
        data = self.request[0].strip()
        socket = self.request[1]
        print("{} wrote:".format(self.client_address[0]))
        print(data)
        socket.sendto(data.upper(), self.client_address)

if __name__ == "__main__":
    HOST, PORT = "localhost", 9999
    with socketserver.UDPServer((HOST, PORT), MyUDPHandler) as server:
        server.serve_forever()