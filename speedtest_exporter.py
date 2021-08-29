import json
import flask
import subprocess
import time
import threading
from flask import Flask
import datetime
from prometheus_client import make_wsgi_app, Gauge
import os
import argparse

def start_thread(func, name=None, args = []):
    threading.Thread(target=func, name=name, args=args).start()

def run_speedtest(delay,id,hostname):
    if delay == '':
        speedtest_delay = '600'
    else:
        speedtest_delay = delay

    if id == '':
        server_id = ''
    else:
        server_id = id
    
    if hostname == '':
        server_hostname = ''
    else:
        server_hostname = hostname

    if server_hostname == '' and server_id != '':
        cmd_arg = ' -s '+server_id
    elif server_id == '' and server_hostname != '':
        cmd_arg = ' -o '+server_hostname
    else:
        cmd_arg = ''
    
    while True:
        tmpd = {}
        cmd = 'speedtest -f json'+cmd_arg
        cmd = cmd.split()
        sp = subprocess.Popen(cmd,shell=False,stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
        sp.wait()
        out,err = sp.communicate()
        global data
        tmpd = json.loads(out)
        tmpd['download']['speed'] = "{:.2f} Mbit/s".format(int(tmpd['download']['bytes']) * 8 / 1024 / 1024 / int(int(tmpd['download']['elapsed']) / 1000))
        tmpd['upload']['speed'] = "{:.2f} Mbit/s".format(int(tmpd['upload']['bytes']) * 8 / 1024 / 1024 / int(int(tmpd['upload']['elapsed']) / 1000))
        tmpd['interface'].pop('internalIp')
        tmpd['interface'].pop('isVpn')
        tmpd['interface'].pop('macAddr')
        tmpd['interface'].pop('name')
        tmpd['server'].pop('location')
        tmpd['server'].pop('country')
        tmpd['server'].pop('ip')
        tmpd['server'].pop('name')
        tmpd['server'].pop('port')
        tmpd['result'].pop('id')
        tmpd.pop('type')
        data = tmpd
        time.sleep(speedtest_delay)   

def run_http(ip,port):
    app = Flask(__name__)

    server = Gauge('speedtest_server_id', 'Speedtest server ID used to test')
    jitter = Gauge('speedtest_jitter_latency_milliseconds','Speedtest current Jitter in ms')
    ping = Gauge('speedtest_ping_latency_milliseconds','Speedtest current Ping in ms')
    download_speed = Gauge('speedtest_download_mbits_per_second','Speedtest current Download Speed in Mbit/s')
    upload_speed = Gauge('speedtest_upload_mbits_per_second','Speedtest current Upload speed in Mbit/s')
    packetloss = Gauge('speedtest_packetloss_percentage', 'Speedtest packetloss percentage')

    @app.route('/')
    def get_data():
        app.config["JSONIFY_PRETTYPRINT_REGULAR"] = True
        global data 
        return flask.jsonify(data)

    @app.route('/metrics',)
    def metrics():
        global data
        if data == '{}':
            srv,jit,p,dw,up,pkt = 0,0,0,0,0,0
        else:    
            srv,jit,p,dw,up,pkt = data['server']['id'],data['ping']['jitter'],data['ping']['latency'],data['download']['speed'].split()[0],data['upload']['speed'].split()[0],data['packetLoss']

        server.set(srv)
        jitter.set(jit)
        ping.set(p)
        download_speed.set(dw)
        upload_speed.set(up)
        packetloss.set(pkt)
        
        return make_wsgi_app()
    
    app.run(threaded=True,host=ip,port=port)


if __name__ == "__main__":
    global data
    data = '{}'
    parser = argparse.ArgumentParser()
    parser.add_argument('--delay','-d',nargs="?",default='600')
    parser.add_argument('--server_id','-id',nargs="?",default='')
    parser.add_argument('--server_host','-hst',nargs="?",default='')
    parser.add_argument('--listen_port',nargs="?", default='8081')
    parser.add_argument('--listen_ip',nargs="?",default='localhost')
    args = parser.parse_args()
    dly,sid,sh,lp,lip = args.delay,args.server_id,args.server_host,args.listen_port,args.listen_ip
    
    if 'SPEEDTEST_DELAY' in os.environ:
        dly = os.environ['SPEEDTEST_DELAY']
    if 'SPEEDTEST_SERVER_ID' in os.environ:
        sid = os.environ['SPEEDTEST_SERVER_ID']
    if 'SPEEDTEST_SERVER_HOST' in os.environ:
        sh = os.environ['SPEEDTEST_SERVER_HOST']
    if 'SPEEDTEST_EXPORTER_LISTEN_PORT' in os.environ:
        lp = os.environ['SPEEDTEST_EXPORTER_LISTEN_PORT']
    if 'SPEEDTEST_EXPORTER_LISTEN_IP' in os.environ:
        lip = os.environ['SPEEDTEST_EXPORTER_LISTEN_IP']

    start_thread(run_speedtest,args = [dly,sid,sh])
    run_http(lip,lp)

    
