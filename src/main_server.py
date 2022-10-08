from calendar import c
import socketserver
from gc import collect
from typing import Dict, Optional, List
from pymongo import errors
import fastapi, json
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
import cachetools, re, socket, time, hashlib, uuid
from concurrent.futures import ThreadPoolExecutor


formatter = logging.Formatter("%(asctime)s loglevel=%(levelname)-6s logger=%(name)s %(funcName)s() L%(lineno)-4d %(message)s   call_trace=%(pathname)s L%(lineno)-4d")
logger = logging.getLogger("app")
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
ch.setFormatter(formatter)
logger.addHandler(ch)

app = FastAPI()
app.add_middleware(PrometheusMiddleware)

caches_set = {}
ttl_cache = cachetools.TTLCache(maxsize=1000000, ttl=300)
operations_done = cachetools.TTLCache(maxsize=1000, ttl=300)

udpExecutor = ThreadPoolExecutor(max_workers=2)

class ResponseModel(BaseModel):
    message: str
    data: Optional[List[str] | Dict | str | None]

class UDPRequest(BaseModel):
    action: str
    path: str | None
    content: str | None
    operationId: str | None


@app.get("/items/{cache_name}/with_id/{id}", status_code=200, response_model=ResponseModel)
async def get_path(cache_name: str, id: str, response: fastapi.Response) -> ResponseModel:
    """just try to get the element

    Args:
        cache_name (str): name of cache
        id (str): id of element

    Returns:
        ResponseModel: a response
    """
    
    logger.info(f"trying to locate {id} in {cache_name}, having {caches_set.keys()}")
    if id in caches_set[cache_name].keys():
        return ResponseModel(message="success", data=caches_set[cache_name][id])
    response.status_code = 404
    return ResponseModel(message="not found", data=None)

@app.get("/items/{cache_name}/keys", status_code=200, response_model=ResponseModel)
async def get_keys(cache_name :str, response: fastapi.Response) -> ResponseModel:
    """just try to get the element

    Args:
        cache_name (str): 

    Returns:
        ResponseModel: a response
    """
    if cache_name in caches_set.keys():
        dat = list(caches_set[cache_name].keys())
        return ResponseModel(message="data", data=dat)
    response.status_code = 404
    return ResponseModel(message=f"{cache_name} not found in {caches_set.keys()}", data=None)

@app.get("/items/names", status_code=200, response_model=ResponseModel)
async def get_caches(response: fastapi.Response) -> ResponseModel:
    """just try to get the element

    Args:

    Returns:
        ResponseModel: a response
    """
    return ResponseModel(message="data", data=list(caches_set.keys()))

@app.get("/operations", status_code=200, response_model=ResponseModel)
async def get_operations(response: fastapi.Response) -> ResponseModel:
    """just try to get the element

    Args:

    Returns:
        ResponseModel: a response
    """
    keys = list(operations_done.keys())
    data = list(map(lambda x : operations_done[x], keys))
    return ResponseModel(message="data", data=data)

@app.get("/sync", status_code=200, response_model=ResponseModel)
async def get_operations(response: fastapi.Response) -> ResponseModel:
    """just try to get the element

    Args:

    Returns:
        ResponseModel: a response
    """
    keys = list(operations_done.keys())
    data = list(map(lambda x : operations_done[x], keys))
    send_broadcast("sync", "NA.NA", "NA")

@app.post("/items/{cache_name}/{id}", status_code=201, response_model=str)
async def post_path(cache_name: str, id: str, item: str):
    """post the element

    Args:
        cache_name (str): 
        id (str): id 
        item (str): data

    Returns:
        str: data
    """
    # if cache_name not in caches_set create it
    if cache_name not in caches_set.keys():
        caches_set[cache_name] = cachetools.TTLCache(maxsize=1000000, ttl=300)
    # now we are sure it is created
    caches_set[cache_name][id] = item
        
    logger.info(f"trying to store {id} in {cache_name}")
    
    # send a message to everyone to update their cache
    send_broadcast("set", f"{cache_name}.{id}", item)
    return item

@app.on_event("startup")
async def prepare_things():
    env = dict(os.environ)
    try:
        # t = Thread(target=start_http_server, args=(8000))
        logger.info("-"*15 +  "creating udp server" + "-" * 15)
        t2 = Thread(target=start_udp_server)
        # t.start()
        t2.start()
    except OSError as e:
        # it just means a worker already opened the server, so pass through
        pass

    

def start_udp_server():
    HOST, PORT = "0.0.0.0", 9999
    with socketserver.UDPServer((HOST, PORT), MyUDPHandler) as server:
        server.serve_forever()


class MyUDPHandler(socketserver.BaseRequestHandler):
    
    def set(self, udpReq: UDPRequest):
        
        action, path, operationId, content = udpReq.action, udpReq.path, udpReq.operationId, udpReq.content
        cache_name, id = path.split(".")
        if cache_name not in caches_set.keys():
            caches_set[cache_name] = cachetools.TTLCache(maxsize=1000000, ttl=300)
        caches_set[cache_name][id] = content
        operations_done[operationId] = udpReq.json()
    
    def do_many(self, content ):
        els = json.loads(content)
        logger.info(f"iterating over {content}")
        for el in els:
            logger.info(f"element iterated: {json.dumps(el)}")
            operationId, data = el[0], json.loads(el[1])
            if data["operationId"] in operations_done.keys():
                continue
            newUdpReq = UDPRequest(**el)
            self.set(newUdpReq)
    
    def del_key(self, cache_name, id):
        if cache_name in caches_set.keys():
            if id in caches_set[cache_name].keys():
                del caches_set[cache_name][id]
        
    
    """
    This class works similar to the TCP handler class, except that
    self.request consists of a pair of data and client socket, and since
    there is no connection the client address must be given explicitly
    when sending data back via sendto().
    """

    def handle(self):
        """Just a distpatcher for the threadpool executor
        """
        data = self.request[0].strip()
        socket = self.request[1]
        udpReq = UDPRequest(**json.loads(data.decode("utf-8")))
        action, path, operationId, content = udpReq.action, udpReq.path, udpReq.operationId, udpReq.content
        cache_name, id = path.split(".")
        if operationId in operations_done:
            return
        if action == "set":
            logger.info(f"trying to set {id} in {cache_name} with {content}, having {caches_set.keys()}")
            udpExecutor.submit(self.set, udpReq)
        elif action == "delete":
            udpExecutor.submit(self.del_key, cache_name, id)
        elif action == "get":
            socket.sendto(ttl_cache[path], self.client_address)
        # for synchronizing up caches
        elif action == "recall":
            udpExecutor.submit(socket.sendto, operations_done[operationId], self.client_address)
            # socket.sendto(operations_done[operationId], self.client_address)
        elif action == "list_operations":
            udpExecutor.submit(socket.sendto, str(list(operations_done.keys())), self.client_address)
            # socket.sendto(str(list(operations_done.keys())), self.client_address)
        elif action == "sync":
            udpExecutor.submit(self.not_so_delayed_sync, 5)
        elif action == "do_many":
            udpExecutor.submit(self.do_many, content)
                
        logger.info(f"UDP server received: {action} to {path} with {operationId} and content {content} from {self.client_address}")
        
    
    def not_so_delayed_sync(self, timeout: int = 5):
        # wait_time = random.random() * timeout
        # time.sleep(wait_time)
        k = list(operations_done.keys())
        operations = list(operations_done.items())
        send_broadcast("do_many", "NA.NA", json.dumps(operations))
    

def resend_operation(operation):
    interfaces = socket.getaddrinfo(host=socket.gethostname(), port=None, family=socket.AF_INET)
    allips = [ip[-1][0] for ip in interfaces]

    # msg = b'hello world'
    for ip in allips:
        print(f'sending on {ip}')
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)  # UDP
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.bind((ip,0))
        msg = bytes(operation, "utf-8")
        logger.info(f"sending {msg} through all interfaces")
        sock.sendto(msg, ("255.255.255.255", 9999))
        sock.close()

def send_broadcast(action, path, content):
    interfaces = socket.getaddrinfo(host=socket.gethostname(), port=None, family=socket.AF_INET)
    allips = [ip[-1][0] for ip in interfaces]
    operationId = uuid.uuid3(uuid.NAMESPACE_DNS, f"{action}{path}{content}{time.time()}").hex
    udpReq = UDPRequest(action=action, path=path, operationId=operationId, content=content)
    msg = bytes(udpReq.json(), "utf-8")
    # msg = b'hello world'
    for ip in allips:
        print(f'sending on {ip}')
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)  # UDP
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.bind((ip,0))
        logger.info(f"sending {msg} through all interfaces")
        sock.sendto(msg, ("255.255.255.255", 9999))
        sock.close()
    if action not in ["sync", "do_many", "recall", "list_operations"]:
        operations_done[operationId] = udpReq.json()
    