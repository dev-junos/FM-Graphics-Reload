"""Read-only live state monitor and renewable, game-thread-owned apply lease."""
import ctypes as C
import threading
import time
import secrets
import client


def read(pid=None):
    if pid is None:
        pids=client.fm_pids()
        if len(pids)!=1:return dict(state='missing' if not pids else 'multiple',pid=None)
        pid=pids[0]
    mapping=client.K.OpenFileMappingW(4,False,f'Local\\{client.BRIDGE_MAPPING}_{pid}')
    if not mapping:return dict(state='disconnected',pid=pid)
    ptr=None
    try:
        ptr=client.K.MapViewOfFile(mapping,4,0,0,C.sizeof(client.Wire))
        if not ptr:return dict(state='unknown',pid=pid)
        wire=client.Wire.from_buffer_copy(C.string_at(ptr,C.sizeof(client.Wire)))
        now=client.K.GetTickCount64()
        if wire.magic!=0x464d475241504831 or wire.version!=1:return dict(state='unknown',pid=pid)
        if not wire.status_tick or now-wire.status_tick>2000 or now-wire.heartbeat>2000:return dict(state='unresponsive',pid=pid)
        if wire.state==4 and wire.code==21:return dict(state='restart',pid=pid)
        state={0:'unknown',1:'idle',2:'busy',3:'locked'}.get(wire.activity,'unknown')
        if wire.state in (1,2):state='locked'
        return dict(state=state,pid=pid,world=wire.observed_world,stamp=wire.status_tick)
    finally:
        if ptr:client.K.UnmapViewOfFile(ptr)
        client.K.CloseHandle(mapping)


def connect():
    pids=client.fm_pids()
    if len(pids)!=1:raise RuntimeError('FM26을 한 개 실행하고 저장된 게임을 불러와 주세요.')
    client.install(pids[0])
    for _ in range(30):
        result=read(pids[0])
        if result['state'] not in ('unknown','unresponsive','disconnected'):return result
        time.sleep(.1)
    return result


class Guard:
    def __init__(self,pid):
        self.pid=pid;self.session=None;self.stop=threading.Event();self.thread=None;self.token=0

    def __enter__(self):
        from skins import Session
        if client.request_token():raise RuntimeError('다른 적용 작업이 실행 중입니다.')
        try:
            self.session=Session(self.pid).__enter__()
            self.token=secrets.randbits(63) or 1
            client.guard_context.token=self.token
            self.session.wire.lease_until=client.K.GetTickCount64()+5000
            self.session.command(4,'')
            if self.session.wire.guard_token!=self.token:raise RuntimeError(client.ERRORS[25])
            self.thread=threading.Thread(target=self.renew,daemon=True);self.thread.start()
            return self
        except BaseException:
            self.__exit__(None,None,None);raise

    def renew(self):
        while not self.stop.wait(1):
            if self.session.wire.guard_token!=self.token:return
            self.session.wire.lease_until=client.K.GetTickCount64()+5000

    def __exit__(self,exc_type,exc,tb):
        # On a timeout, stop renewing and let the in-game watchdog release after
        # its outstanding operation finishes. Never overwrite a pending request.
        try:
            if self.session and self.session.ptr and self.token:
                wire=self.session.wire
                if wire.guard_token==self.token and wire.state not in (1,2) and not (wire.state==4 and wire.code==21):
                    self.session.command(5,'')
        finally:
            self.stop.set()
            if self.thread:self.thread.join(2)
            client.guard_context.token=0
            if self.session:self.session.__exit__(exc_type,exc,tb)
