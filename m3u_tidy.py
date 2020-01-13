# -*- coding: utf-8 -*-
# more info on the M3U file format available here:
# http://n4k3d.com/the-m3u-file-format/

import sys, os, subprocess, signal
import re
import requests, urllib3
from math import floor
from zhconv.zhconv import convert
from enum import Enum, unique

supports_m3u = ['http','https','rtmp','rstp','ftp']
supports_chk = ['http','https','rtmp','rstp','ftp','sop','vjms','mitv','p2p','p3p','p4p','p5p','p6p','p7p','p8p','p9p']
playlist = []
service_map = []
groups = []
lineEnds = '\n'
force_get_name = False
need_check_service_status = False
flag_sync_to_reference = False
map_file = ''
action_dsd = ''

@unique
class Flag(Enum):
    REFERENCE   = 1
    OUTPUT      = 2
    UPDATED     = 4
    SKIP        = 8
    MAP_GROUP   = 16
    MAP_CHANNEL = 32

    def __int__(self):
        return self.value

class track():
    def __init__(self, length, group, id, name, logo, title, path, fname, flag, fixed_name):
        self.id = id
        self.length = length
        self.group = group
        self.name = name
        self.logo = logo
        self.title = title
        self.path = path
        self.fname = fname
        self.flag = flag
        self.fixed_name = fixed_name

"""
    song info lines are formatted like:
    EXTINF:419,Alice In Chains - Rotten Apple
    length (seconds)
    Song title
    file name - relative or absolute path of file
    ..\Minus The Bear - Planet of Ice\Minus The Bear_Planet of Ice_01_Burying Luck.mp3
"""

class service_map_item():
    def __init__(self, flag, name, nickname):
        self.flag = flag
        self.name = name
        self.nickname = nickname

def shutdown_me(signum, frame):
    print('')
    exit()

def isdsd(url):
    result = re.search(r'\/dsdtv\/', url) != None
    if re.search(r'\/\/cloud-play\.hhalloy\.com\/live\/', url) != None:
        uuid = os.path.splitext(os.path.split(url)[1])[0]
        result = result or (re.match(r'\w{32,}$', uuid) != None)
    return result

def get_url_uuid(url):
    uuid = os.path.splitext(os.path.split(url.split('$')[0])[1])[0]
    if re.match(r'\w{32,}$', uuid) != None:
        return uuid
    else:
        return ''

def resort_playlist():
    i = 0
    for item in playlist:
        if item.flag == int(Flag.OUTPUT):
            break
        if item.flag == int(Flag.REFERENCE) and i < len(playlist):
            if item.group not in groups:
                continue
            found_group = False
            for mapitem in service_map:
                if mapitem.nickname.strip() == item.group.strip() and mapitem.flag == Flag.MAP_GROUP:
                    item.group = mapitem.name.strip()
            for j in range(i + 1, len(playlist)):
                if found_group:
                    if item.group != playlist[j].group:
                        if need_check_service_status:
                            print(F'      Checking to add: {item.title} ...{" ":40}')
                        if ((need_check_service_status  and chk_service_status(item.path) or not need_check_service_status)):
                            item.flag |= int(Flag.OUTPUT)
                            playlist.insert(j - 1, item)
                            playlist.remove(playlist[i])
                            break
                elif item.group == playlist[j].group and item.flag == int(Flag.OUTPUT):
                    found_group = True

        i = i + 1

def chk_service_status(url):
    url_base_items = url.split("://")
    protocol = url_base_items[0]
    if protocol not in supports_chk:
        return True

    if protocol == 'http' or protocol == 'https':
        userAgent = {"user-agent": "Mozilla/5.0 (X11; Linux x86_64; rv:72.0) Gecko/20100101 Firefox/72.0"}
        session = requests.Session()
        try:
            session.trust_env = False
            request = session.get(url, headers = userAgent, timeout = 10)
            httpStatusCode = request.status_code
            if request.status_code == 200:
                return True
            else:
                return False
        except  (requests.exceptions.ConnectTimeout, requests.exceptions.ConnectionError,urllib3.exceptions.MaxRetryError, urllib3.exceptions.ReadTimeoutError):
            if os.environ[protocol+'_proxy'] != '':
                try:
                    session.trust_env = True
                    request = session.get(url, headers = userAgent, timeout = 20)
                    httpStatusCode = request.status_code
                    if request.status_code == 200:
                        return True
                except:
                    pass
        except:
            pass
        return False

    # for other protocols
    port = 0
    server_and_port = url_base_items[1].split("/")[0].split(":")
    server = server_and_port[0].split('$')[0]
    if len(server.split('@')) > 1:
        server = server.split('@')[1]

    if len(server_and_port) == 1:
        if protocol == 'rtmp':
            port = 1935
    else:
        port = int(server_and_port[1])
    if port > 0:
        cmd = F'nmap -sT -n --max-rtt-timeout 1 --max-scan-delay 1ms --host-timeout 2 -Pn -p {port} {server}'
    else:
        cmd = F'nmap -sT -n --max-rtt-timeout 1 --max-scan-delay 1ms --host-timeout 2 -Pn {server}'
    outputs = subprocess.Popen(cmd,stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True).communicate()
    output = outputs[0].decode()
    if output.find('(0 hosts up)') >= 0:
        return False
    else:
        return True

def parse_service_map(infile):
    global service_map
    try:
        assert(type(infile) == '_io.TextIOWrapper')
    except AssertionError:
        infile = open(infile, "r")
    for line in infile:
        line = line.strip()
        if line == '':
            continue
        flag = Flag.MAP_CHANNEL
        if len(line.split(':')) > 1:
             typename = line.split(':')[0].strip()
             line = line.split(':')[1].strip()
             if typename.upper() == 'GROUP':
                flag = Flag.MAP_GROUP
             elif typename.upper() == 'CHANNEL':
                flag = Flag.MAP_CHANNEL
             else:
                continue
        name,nick = line.split(',')
        name = name.strip()
        nick = nick.strip().split(' ')[0].split('#')[0].strip()
        found = False
        for item in service_map:
            if item != None and item.name == name and item.nickname == nick \
                   and item.name != '' and item.nick != '' and item.item != None and item.nickname != None \
                   and item.flag != '' and item.flag == flag:
                found = True
                break
        if not found:
            map_item = service_map_item(flag, name, nick)
            service_map.append(map_item)

    infile.close()

def parsem3u(infile, need):
    global lineEnds, flag_sync_to_reference, action_dsd
    ifile = infile
    try:
        assert(type(infile) == '_io.TextIOWrapper')
    except AssertionError:
        infile = open(infile,'rb')

    """
        All M3U files start with #EXTM3U.
        If the first line doesn't start with this, we're either
        not working with an M3U or the file we got is corrupted.
    """

    line = infile.readline()
    if line[0:7] != b'#EXTM3U':
       return
    if need and line.splitlines(True)[0][-2:-1] == b'\r':
        lineEnds='\r\n'

    infile.close()
    maxLines = int(os.popen(F'wc -l {ifile}').read().split()[0])
    infile = open(ifile, 'r')
    # initialize playlist variables before reading file
    song=track(None, None, None, None, None, None, None, None, None, None)
    line_no = 0
    output_line_maxlen = 0
    for line in infile:
        skip_line = False
        line=line.strip()
        line_no += 1
        percent = floor((line_no * 100) / maxLines)

        if line.startswith('#EXTINF:') or line.startswith('EXTINF:'):
            # pull length and title from #EXTINF line
            paramstr = ""
            title = ""
            id = -1
            name = ""
            logo = ""
            group = ""
            commaing = False
            isTitle = False
            item = ""
            lastchar = ""
            fixed_name = ""
            param = []
            for c in line.split('EXTINF:')[1]:
                 if c == "\"" or c == "\'":
                     if commaing == False:
                         commaing = True
                     else:
                         commaing = False

                     if isTitle == False:
                         item = item + c
                     else:
                         title = title + c
                 elif commaing == False and c == ",":
                     isTitle = True
                     if item != "":
                        param.append(item)
                        item = ""
                 elif lastchar != "" and lastchar.isspace() and c.isspace():
                     continue
                 elif commaing == False and c != "" and c.isspace() and isTitle == False and item != "":
                     param.append(item)
                     item = ""
                 else:
                     if isTitle == False:
                         item = item + c
                     else:
                         title = title + c
                 lastchar = c         

            title = title.strip()
            process_msg = F'      processed: {percent:2}%  processing: '
            if output_line_maxlen < (len(process_msg) + len(title)):
               output_line_maxlen = len(process_msg) + len(title)
            print(process_msg + F'{title:{output_line_maxlen - len(process_msg)}}', end='\r')
            name = ""
            group = ""
            logo = ""
            length = 0
            i = 0
            for item in param:
                i = i + 1
                if i==1:
                   length = item
                   continue
                param_name,param_value=item.split('=',1)
                param_name = param_name.strip()
                param_value = re.sub('\"','',param_value)
                if param_name == "tvg-id":
                    try:
                        id = int(param_value)
                    except:
                        id = -1
                if param_name == "tvg-name":
                    name = param_value
                elif param_name == "tvg-logo":
                    logo = re.sub(",", "%2C", param_value)
                elif param_name == "group-title":
                    group = param_value
                elif param_name == "fixed-name" and param_value.upper() == "TRUE":
                    fixed_name = True
            if need:
                song=track(length, group, id, name, logo, title, None, None, int(Flag.OUTPUT), fixed_name)
                found_group = False
                if group not in groups:
                    groups.append(group)
            else:
                song=track(length, group, id, name, logo, title, None, None, int(Flag.REFERENCE), fixed_name)
        elif (len(line.strip()) != 0):
            # pull song path from all other, non-blank lines
            protocol = line.strip().split('://')[0]
            if protocol not in supports_m3u:
                 song=track(None, None, None, None, None, None, None, None, None, None)
                 continue
            song.path=re.sub(",.*","",line)
            fname = get_url_uuid(song.path)
            if need_check_service_status and need and chk_service_status(song.path) == False:
                song=track(None, None, None, None, None, None, None, None, None, None)
                continue

            title_mapped = False
            for mapitem in service_map:
                if mapitem.flag == Flag.MAP_CHANNEL and mapitem.nickname == song.title:
                    song.title == mapitem.name
                    title_mapped = True
                    break
            for mapitem in service_map:
                if mapitem.flag == Flag.MAP_GROUP and mapitem.nickname == song.group:
                    song.group == mapitem.name
                    break

            # skip duplicate list item
            found_service = False
            found_path = False
            for item in playlist:
                #print(F'line {line_no}: title:{song.title} {line}')
                if (song.path != '' and song.path == item.path) \
                        or re.sub('-| ', '', re.sub(r'(?P<xdian>[^电])台$|HD$|高清$|频道$|\s*\[dsd\]$','\g<xdian>', convert(song.title, "zh-cn"))) \
                            == re.sub('-| ', '', re.sub(r'(?P<xdian>[^电])台$|HD$|高清$|频道$|\s*\[dsd\]$','\g<xdian>', convert(item.title, "zh-cn"))) \
                        or re.sub(r'(?P<xdian>[^电])台$|HD$|频道$|\s*\[dsd\]$','\g<xdian>', convert(song.title, "zh-cn")) \
                            == re.sub(r'(?P<xdian>[^电])台$|HD$|频道$','\g<xdian>', convert(item.name, "zh-cn")):
                    found_service = True
                    if item.path == song.path:
                        found_path = True
                        if item.group == song.group and item.flag == song.flag:
                            skip_line = True
                            continue
                    if item.flag == Flag.REFERENCE:
                        item.flag |= Flag.UPDATED

            if skip_line or ((song.flag & int(Flag.REFERENCE)) == 0 and flag_sync_to_reference and found_service == True and found_path == False):
                song=track(None, None, None, None, None, None, None, None, None, None)
                continue

            if song.fname != "" and (song.name == "" or song.logo == "" or song.id == ""):
                for item in playlist:
                    if item.fname == fname and item.fname != "" and item.name != "":
                        if item.name != "":
                            song.name = item.name
                        if item.logo != "":
                            song.logo = item.logo
                        if item.id != "":
                            song.id = item.id
                        if not title_mapped:
                            song.title = re.sub('-| ', '', re.sub(r'(?P<xdian>[^电])台$|HD$|高清$','\g<xdian>', convert(song.title,"zh-cn"))) 
                        break

            if song.name == "" or (force_get_name):
                for item in playlist:
                    if re.sub('-| ', '', re.sub(r'(?P<xdian>[^电])台$|HD$|高清$|频道$|\s*\[dsd\]$','\g<xdian>', convert(song.title,"zh-cn"))) \
                       == re.sub('-| ', '', re.sub(r'(?P<xdian>[^电])台$|HD$|高清$|频道$|\s*\[dsd\]$','\g<xdian>', convert(item.title,"zh-cn"))) \
                          or (item.name != "" and \
                            re.sub(r'(?P<xdian>[^电])台$|HD$|频道$|\s*\[dsd\]$','\g<xdian>', convert(song.title,"zh-cn")) \
                            == re.sub(r'(?P<xdian>[^电])台$|HD$|频道$','\g<xdian>', convert(item.name,"zh-cn"))):
                        if item.name != "" and (song.name == "" or (song.name != "" and song.fixed_name != True)):
                            song.name = item.name
                        if item.logo != "":
                            song.logo = item.logo
                        if item.id != "":
                            song.id = item.id
                        if not title_mapped:
                            song.title = re.sub(r'台$|臺$','', song.title)
                        break

            if song.name == "" and need:
               song.name = re.sub(r'(?P<xdian>[^电])台$|HD$|\s*\[dsd\]$','\g<xdian>', convert(song.title,"zh-cn"))
               if song.name[0:5] == 'CCTV-' or song.name[0:5] == 'CCTV_':
                   song.name = song.name[0:4] + song.name[5:]

            if action_dsd == 'mark' and isdsd(song.path) and re.search('\[dsd\]$', song.title) == None:
               if song.title[len(song.title) - 1].encode('UTF-8').isalpha():
                  song.title += ' '
               song.title += '[dsd]'
            elif action_dsd == 'unmark':
               song.title = re.sub(r'(?P<xdian>)\s*\[dsd\]$','\g<xdian>', song.title)
            elif action_dsd == 'remove' and isdsd(song.path):
                song.path = ''

            if song.logo == "" and song.path != '':
               for item in playlist:
                    if song.name == item.name and song.name != "":
                        song.logo = item.logo
                        break

            if song.path != '':
                playlist.append(song)

            # reset the song variable so it doesn't use the same EXTINF more than once
            song=track(None, None, None, None, None, None, None, None, None, None)
        else:
            song=track(None, None, None, None, None, None, None, None, None, None)

    infile.close()

    return playlist

def parsetxt(infile, need):
    global lineEnds, flag_sync_to_reference, action_dsd

    ifile = infile
    try:
        assert(type(infile) == '_io.TextIOWrapper')
    except AssertionError:
        infile = open(infile,'rb')

    line = infile.readline()
    if len(line) >= 7 and line[0:7] == b'#EXTM3U':
       print(F'{infile} could be m3u file, not txt format tvlist.')
       return
    if need and line.splitlines(True)[0][-2:-1] == b'\r':
        lineEnds='\r\n'

    infile.close()

    maxLines = int(os.popen(F'wc -l {ifile}').read().split()[0])
    infile = open(ifile, 'r')
    # initialize playlist variables before reading file
    song=track(None, None, None, None, None, None, None, None, None, None)
    group = ""
    line_no = 0
    output_line_maxlen = 0
    for line in infile:
        line_no += 1
        percent = floor((line_no * 100) / maxLines)

        line=line.strip()
        if line != "":
            # pull length and title from #EXTINF line
            title = ""
            param = []
            if line.split(',')[1].strip() == '#genre#':
                group = line.split(',')[0].strip()
                for mapitem in service_map:
                    if mapitem.flag == Flag.MAP_GROUP and mapitem.nickname == group:
                        group == mapitem.name
                        break
                if need and (group not in groups):
                    groups.append(group)
                continue

            skipme = False
            title = line.split(',')[0].strip()
            path = line.split(',')[1].strip()

            process_msg = F'      processed: {percent:2}%  processing: '
            if output_line_maxlen < (len(process_msg) + len(title)):
               output_line_maxlen = len(process_msg) + len(title)
            print(process_msg + F'{title:{output_line_maxlen - len(process_msg)}}', end='\r')

            title_mapped = False
            for mapitem in service_map:
                if mapitem.flag == Flag.MAP_CHANNEL and mapitem.nickname == title:
                    title == mapitem.name
                    title_mapped = True
                    break

            urls = path.split('#')
            path = ''
            i = 0
            for item in urls:
                j = 0
                foundme = False
                simple_item = re.sub(r'\$*', '', item).strip()
                uuid_item = get_url_uuid(item)
                while j < i:
                    simple_item_j = re.sub(r'\$*','',urls[j]).strip()
                    if simple_item == simple_item_j or (uuid_item != '' and uuid_item == get_url_uuid(urls[j])):
                        foundme = True
                        if re.sub(r'\.m3u8|\.flv', '', simple_item) == re.sub(r'\.m3u8|\.flv', '', simple_item_j) \
                               and os.path.splitext(re.sub(r'\$.*', '', simple_item))[1] == '.m3u8' \
                               and  os.path.splitext(re.sub(r'\$.*', '', simple_item_j))[1] == '.flv':
                            label = ''
                            if len(urls[j].split('\$')) > 1:
                                label = '$' + urls[j].split('\$')[1]
                            urls[j] = os.path.splitext(re.sub(r'\$.*', '', urls[j]))[0] + '.m3u8' + label
                        break
                    j += 1

                if foundme or (need_check_service_status and need and chk_service_status(item) == False):
                    urls[i] = ''
                    i += 1
                    continue

                for list_item in playlist:
                    if re.sub('-| ', '', re.sub(r'(?P<xdian>[^电])台$|HD$|高清$|频道$|\s*\[dsd\]$','\g<xdian>', convert(title, "zh-cn"))) \
                            == re.sub('-| ', '', re.sub(r'(?P<xdian>[^电])台$|HD$|高清$|频道$|\s*\[dsd\]$','\g<xdian>', \
                                    convert(list_item.title, "zh-cn"))):
                        foundit = False
                        allow_write_back = (not flag_sync_to_reference) or (list_item.flag & int(Flag.REFERENCE)) == 0
                        url_items = list_item.path.split("#")
                        jj = 0
                        for url_item in url_items:
                            simple_url_item = re.sub(r'\$*','',url_item).strip()
                            if simple_url_item == simple_item or (uuid_item != '' and uuid_item == get_url_uuid(url_item)):
                                foundit = True
                                if allow_write_back \
                                       and re.sub(r'\.m3u8|\.flv', '', simple_item) == re.sub(r'\.m3u8|\.flv', '', simple_url_item) \
                                       and os.path.splitext(re.sub(r'\$.*', '', simple_item))[1] == '.m3u8' \
                                       and os.path.splitext(re.sub(r'\$.*', '', simple_url_item))[1] == '.flv':
                                    label = ''
                                    if len(url_items[jj].split('\$')) > 1:
                                         label = '$' + url_items[jj].split('\$')[1]
                                         url_items[jj] = os.path.splitext(re.sub(r'\$.*', '', url_items[jj]))[0] + '.m3u8' + label
                                break
                            jj += 1
                        if not allow_write_back:
                            if not foundit:
                                urls[i] = ''
                        else:
                            list_item.path = ''
                            for url_item in url_items:
                                if list_item.path != '':
                                    list_item.path += '#'
                                list_item.path += url_item

                            if foundit == False:
                                if list_item.flag:
                                    if list_item.group == group:
                                        skipme = True
                                        list_item.path += "#" + item.strip()
                                    else:
                                        item = list_item.path + "#" + item.strip()
                                else:
                                    item = item.strip() + "#" + list_item.path
                        if list_item.flag == int(Flag.REFERENCE):
                            list_item.flag |= int(Flag.UPDATED)
                i += 1

            path = ''
            dsdurl = ''    #dsd url will be low priority
            for item in urls:
                if item != '':
                    if len(item.split('$')) == 1 and isdsd(item) and action_dsd == 'mark':
                        item += '$电视多'
                    elif len(item.split('$')) == 2 and item.split('$')[1] == '电视多' and action_dsd == 'unmark':
                        item = re.sub(r'\$电视多','',item)
                    elif action_dsd == 'remove' and isdsd(item):
                        item = ''
                        continue

                    if isdsd(item):
                        if dsdurl != '':
                            dsdurl += '#'
                        dsdurl += item
                        continue
                    if path != "":
                       path += '#'
                    path += item
            if dsdurl != '':
               if path != '':
                   path += '#'
               path += dsdurl
            if not title_mapped:
                title = re.sub('(?P<xdian>[^电])台$|HD$|高清$','\g<xdian>', convert(title, "zh-cn"))
            if path != '':
                if need:
                    song=track(0, group, None, None, None, title, path, None, int(Flag.OUTPUT), None)
                else:
                    song=track(0, group, None, None, None, title, path, None, int(Flag.REFERENCE), None)

                if not skipme:
                    playlist.append(song)

                # reset the song variable so it doesn't use the same EXTINF more than once
                song=track(None, None, None, None, None, None, None, None, None, None)

    infile.close()

    return playlist

# for now, just pull the track info and print it onscreen
# get the M3U file path from the first command line argument
def main():
    global force_get_name, need_check_service_status, map_file, flag_sync_to_reference, action_dsd
    i = 0
    lastop = ''
    reference_file = ''
    input_file = ''
    map_file = ''

    signal.signal(signal.SIGINT, shutdown_me)
    signal.signal(signal.SIGTERM, shutdown_me)

    for op in sys.argv:
        if i == 0:
            i = i + 1
            continue
        if lastop == "-r" or lastop == "-rs":
            if os.path.exists(op) and os.path.isfile(op):
                reference_file = os.path.realpath(op)
                if lastop == "-rs":
                   flag_sync_to_reference = True;
        elif lastop == "-m":
            if os.path.exists(op) and os.path.isfile(op):
                map_file = os.path.realpath(op)
        elif op == "-f":
            force_get_name = True
        elif op == "-c" or op == "--check":
            need_check_service_status = True
        elif op == "--mark-dsd":
            action_dsd = "mark"
        elif op == "--unmark-dsd":
            if action_dsd == '':
                action_dsd = "unmark"
        elif op == "--remove-dsd":
            if action_dsd == '':
                action_dsd = "remove"
        elif op != "-r" and op != "-f":
            input_file = os.path.realpath(op)
        lastop = op
        i = i + 1

    if i == 1:
        print("Usage: python3 ",sys.argv[0],' [ -f ] [-c|--check] [-m <service map file>] [-r[s] <reference file>] input_file');
        print("       -f          force get tvg-name from reference file.");
        print("       -r|-rs      reference from other file, and -rs mean sync to reference file.");
        print("       -c|--check  drop offline channel source.");
        print("       --mark-dsd| --unmark-dsd")
        print("                   mark channel that service from dian_shi_duo")
        print("")
        print("       ps: reference file and input file can be m3u or txt file.");
        print("       service map format: line format is \"<target title>,<source title>\".");
        exit()

    if not os.path.exists(input_file) or not os.path.isfile(input_file):
        print("Error: source m3u file %s invalid." % input_file)
        exit()

    if map_file != '':
        print(F'  Reading service map: {map_file}')
        parse_service_map(map_file)

    outfile=os.path.join(os.path.split(input_file)[0], os.path.split(input_file)[1].split(".")[0] + "-new" \
            + os.path.splitext(input_file)[1])
    if reference_file != "" and os.path.exists(reference_file) and os.path.isfile(reference_file):
        print(F'  Parsing reference file: {reference_file} ...')
        if os.path.splitext(reference_file)[1] == '.m3u':
            playlist = parsem3u(reference_file, False)
        elif os.path.splitext(reference_file)[1] == '.txt':
            playlist = parsetxt(reference_file, False)

    print(F'  Parsing input file:     {input_file} ...')
    if os.path.splitext(input_file)[1] == '.m3u':
        playlist = parsem3u(input_file, True)
    elif os.path.splitext(input_file)[1] == '.txt':
        playlist = parsetxt(input_file, True)

    resort_playlist()

    print(F'  Writting output file:   {outfile} ...')
    out = open(outfile, "w+")

    if os.path.splitext(outfile)[1] == '.m3u':
        print("#EXTM3U", end=lineEnds, file=out)
        lastgroup = ""
        for track in playlist:
            if track == None or (track.flag & int(Flag.OUTPUT)) == 0 or track.path == None or track.path == "":
                continue
            info=F'#EXTINF:{track.length}'
            if track.group != '':
                info = info + F' group-title=\"{track.group}\"'
            if track.name != '' and track.name != track.title:
                info = info + F' tvg-name=\"{track.name}\"'
            if track.logo != '':
                info = info + F' tvg-logo=\"{track.logo}\"'
            if track.id != None and track.id != -1:
                info = info + F' tvg-id=\"{str(track.id)}\"'
            if track.fixed_name == True:
                info = info + F' fixed-name=True'
            info = info + F', {track.title}'
            if lastgroup != "" and lastgroup != track.group:
                print("", end=lineEnds, file=out)
            print("%s" % info, end=lineEnds, file=out)
            print("%s" % track.path, end=lineEnds, file=out)
            lastgroup = track.group
    elif os.path.splitext(outfile)[1] == '.txt':
        lastgroup = ""
        for track in playlist:
            if track == None or (track.flag & int(Flag.OUTPUT)) == 0 or track.path == None or track.path == "":
                continue
            if track.group != lastgroup:
                if lastgroup != "":
                   print("", end=lineEnds, file=out)
                lastgroup = track.group
                print("%s,#genre#" % track.group, end=lineEnds, file=out)
            print("%s,%s" % (track.title, track.path), end=lineEnds, file=out)

    out.close()

if __name__ == '__main__':
    main()
