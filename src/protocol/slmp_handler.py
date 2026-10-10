import struct
from src.protocol.base import ParsedRequest, CommandResult
from src.protocol.device_parser import parse_device_mc, parse_device_slmp
from src.protocol.mc_frame_3e import McFrame3E, KNOWN_3E_COMMANDS
from src.protocol.mc_frame_4e import McFrame4E
SLMP_SUBCOMMANDS = {0, 1, 2, 3}
class SlmpHandler(McFrame3E):
    def extract_frame(self, buf: bytearray) -> bytes | None:
        return McFrame4E().extract_frame(buf) if buf[:2] == McFrame4E.SUBHEADER_REQUEST else super().extract_frame(buf)
    def detect(self, data: bytes) -> bool:
        if len(data) < 12: return False
        if data[:2] == McFrame4E.SUBHEADER_REQUEST: off = 15
        elif data[:2] == self.SUBHEADER_REQUEST: off = 11 if len(data) >= 13 and struct.unpack_from("<H", data, 7)[0] + 9 == len(data) else 10
        else: return False
        return len(data) >= off + 4 and struct.unpack_from("<H", data, off)[0] in KNOWN_3E_COMMANDS and struct.unpack_from("<H", data, off + 2)[0] in SLMP_SUBCOMMANDS
    def parse_request(self, data: bytes) -> ParsedRequest:
        is4 = data[:2] == McFrame4E.SUBHEADER_REQUEST
        if is4:
            n=struct.unpack_from("<H",data,11)[0]; cmd=data[15:15+n-2]; req=ParsedRequest(access_path=data[6:11],serial=data[2:4],frame_type="standard-4e"); width=6; parser=parse_device_slmp
        else:
            std=len(data)>=13 and struct.unpack_from("<H",data,7)[0]+9==len(data)
            if std: n=struct.unpack_from("<H",data,7)[0]; cmd=data[11:11+n-2]; req=ParsedRequest(access_path=data[2:7],frame_type="standard-3e")
            else: n=struct.unpack_from("<H",data,6)[0]; cmd=data[10:10+n-2]; req=ParsedRequest(access_path=data[2:6],frame_type="legacy-3e")
            width=6 if len(cmd) >= 12 else 4; parser=parse_device_slmp if width==6 else parse_device_mc
        req.command,req.subcommand=struct.unpack_from("<HH",cmd,0); req.data=cmd[4:]
        if req.command in (0x0401,0x1401):
            typ,addr=parser(cmd[4:4+width]); count=struct.unpack_from("<H",cmd,4+width)[0]; req.devices.append({"type":typ,"address":addr,"count":count})
            if req.command==0x1401:
                size=(count+1)//2 if req.subcommand in (1,3) else count*2; req.data=cmd[6+width:6+width+size]
            else: req.data=b""
        return req
    def build_response(self, parsed, result):
        return McFrame4E().build_response(parsed,result) if parsed and parsed.frame_type=="standard-4e" else super().build_response(parsed,result)
