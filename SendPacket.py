# -*- coding: utf-8 -*-
"""
Created on Wed May 15 23:02:48 2019

@author: DELL
"""

# -*- coding:utf-8 -*-
# 通过给节点发送一个包含指令（send）的数据包来操控节点发送数据

import socket
from DataStructure import *


src = input("Src of this packet (A, B, C, D, E): ")
dest =  input("Dest of this packet (A, B, C, D, E): ")

srcAddr = name2addr(src)

commandSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  #  采用UDP
# commandSocket.bind(('127.0.0.1', 29999))

payload = dest
sendpkt = Packet(Address('127.0.0.1', 29999), srcAddr, payload, 2)
commandSocket.sendto(sendpkt.tojson().encode(), (srcAddr.ip, srcAddr.port))
# © 2019 GitHub, Inc.