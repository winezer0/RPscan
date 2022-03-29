#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import sys
import time
import subprocess
from libs.util import get_portable_path, complex_ports_str_to_port_segment
from concurrent.futures import ThreadPoolExecutor


def port_scan_by_portscan(config):
    current_function_name = sys._getframe().f_code.co_name  # print('当前函数名为:', current_function_name) # check_live_by_nmap
    config[current_function_name] = []
    config.logger.info("[+] 开始通过{}模块进行IP端口检测!!!".format(current_function_name))
    config[current_function_name] = PortscanScan(config).run()
    # 函数结果会返回到以当前函数名命名的config[]字典中。
    return config[current_function_name]


class PortscanScan(object):
    """端口扫描"""

    def __init__(self, config):
        # 基本设置
        super(PortscanScan, self).__init__()
        self.open_ip_port_list = dict()  # 存放IP及其对应的开放端口列表
        self.logger = config.logger
        self.alive_ip_host = config.all_alive_ip_host
        self.ports = config.ports
        self.ignore_ports_flag = config.ignore_ports_flag
        self.run_stop_flag = True

        # 程序设置
        self.program_name = "portscan"
        self.program_path = get_portable_path(config, self.program_name).replace("$BASE_DIR$", str(config.BASE_DIR))
        # self.logger.debug("[*]PATH {}: {}".format(self.program_name, self.program_path))
        # 读取程序必须参数thread_pool_number
        self.thread_pool_number = int(config[self.program_name + '_' + 'thread_pool_number'])
        # 读取程序必须参数port_scan_options
        self.port_scan_options = config[self.program_name + '_' + 'port_scan_options']

        # 其他设置
        self.init_thread()

    def init_thread(self):
        # 设定线程池数量
        # print('优化线程数量...')
        if 0 < len(self.alive_ip_host) < self.thread_pool_number:
            self.thread_pool_number = len(self.alive_ip_host)

    def portscan_scan(self, ip, ports):
        """portscan 端口探测
         Usage of portscan.exe:
           -file             	Use file mode to specify ip address .
           -full             	Scan all TCP and UDP ports in full scan mode. The default is off. By default, only common TCP ports are scanned.
           -ip string           IP to be scanned, supports three formats:192.168.0.1  192.168.0.1-8 192.168.0.0/24
           -p string            Port to be scanned, supports three formats:22,80 22-65535
           -t int             	Maximum number of threads (default 10000)
         """

        if self.run_stop_flag:
            try:
                command = "{} -ip {} -p {} {}".format(self.program_path, ip, ports, self.port_scan_options)
                self.logger.debug('[*] Prospects Command:\n{}'.format(command))

                p = subprocess.Popen(command, bufsize=100000,
                                     stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE)
                # wait until finished
                # get output
                (program_last_output, program_err) = p.communicate()
                program_last_output = bytes.decode(program_last_output)
                self.logger.debug("[*] Program Output:\n{}".format(program_last_output.rsplit("__|", 1)[-1].strip()))
                program_err = bytes.decode(program_err)
                self.portscan_scan_result_analysis(ip, ports, program_last_output)
                # print("program_last_output",program_last_output) #扫描结果
                # print("program_err",program_err) #扫描结果

                # p = Popen(program_command, shell=True, stderr=STDOUT)  # stdout=PIPE,
                # p = Popen(program_command, shell=True, stdout=PIPE, stderr=STDOUT)
                # self.logger.debug("[*]状态：", p.poll())
                # self.logger.debug("[*]开启进程的pid", p.pid)
                # self.logger.debug("[*]所属进程组的pid", os.getpgid(p.pid))
                # time.sleep(90)

            except KeyboardInterrupt:
                time.sleep(1)
                self.logger.error("[-] User aborted.")
                sys.exit(0)
            except Exception as e:
                self.logger.debug(str(e))

    def portscan_scan_result_analysis(self, ip, ports, program_last_output):
        # 从输出结果中正则提取开放IP-端口
        # 注意： match 和 search 是匹配一次 findall 匹配所有
        re_compile = re.compile(r'TCP\]\s{1,4}(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{1,5})')
        tmp_ip_port_list = re_compile.findall(program_last_output)
        # ['192.168.88.1:912', '192.168.88.1:443', '192.168.88.1:902', '192.168.88.1:139', '192.168.88.1:135']
        if len(tmp_ip_port_list) > 0:
            for ip_port in tmp_ip_port_list:
                ip = ip_port.split(':')[0]
                port = int(ip_port.split(':')[-1])
                if ip not in self.open_ip_port_list: self.open_ip_port_list[ip] = []
                self.open_ip_port_list[ip].append(port)

        # 输出IP对应的端口扫描结果
        if ip in self.open_ip_port_list and len(self.open_ip_port_list[ip]) > 0:
            self.logger.debug("[*] {}:{}:{}".format(ip, ports if len(ports) < 20 else str(ports[:20]) + "...",
                                                    self.open_ip_port_list[ip]))
        else:
            self.logger.error("[-] {}:{}:没有扫描到端口".format(ip, ports if len(ports) < 20 else str(ports[:20]) + "..."))

    def run(self):
        # self.logger.info("[+] Start Portscan ports scan...")
        # self.logger.debug('[*]scan ip host: {}'.format(self.all_alive_ip_host))
        try:
            with ThreadPoolExecutor(max_workers=self.thread_pool_number) as executor:
                for ip in self.alive_ip_host:
                    # print("开始发布线程", ip)
                    executor.submit(self.portscan_scan, ip, complex_ports_str_to_port_segment(self.ports))
                    # time.sleep(len(self.ports)/100)
        except KeyboardInterrupt:
            self.logger.error("[-] User aborted.")
            self.run_stop_flag = False
            sys.exit(0)
        except Exception as e:
            self.logger.error(str(e))
            self.run_stop_flag = False
            sys.exit(0)

        return self.open_ip_port_list
