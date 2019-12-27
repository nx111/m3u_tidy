# -*- coding: utf-8 -*-
# more info on the M3U file format available here:
# http://n4k3d.com/the-m3u-file-format/

import sys,os
import re
from zhconv.zhconv import convert

supports = ['http','https','rtmp','rstp','ftp']
playlist = []
lineEnds = '\n'
force_get_name = False

class track():
    def __init__(self, length, group, name, logo, title, path, fname, need, fixed_name):
        self.length = length
        self.group = group
        self.name = name
        self.logo = logo
        self.title = title
        self.path = path
        self.fname = fname
        self.need = need
        self.fixed_name = fixed_name

"""
    song info lines are formatted like:
    EXTINF:419,Alice In Chains - Rotten Apple
    length (seconds)
    Song title
    file name - relative or absolute path of file
    ..\Minus The Bear - Planet of Ice\Minus The Bear_Planet of Ice_01_Burying Luck.mp3
"""

def parsem3u(infile, need):
    global lineEnds

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
    infile = open(ifile, 'r')
    # initialize playlist variables before reading file
    song=track(None, None, None, None, None, None, None, None, None)
    for line in infile:
        line=line.strip()
        if line.startswith('#EXTINF:') or line.startswith('EXTINF:'):
            # pull length and title from #EXTINF line
            paramstr = ""
            title = ""
            name = ""
            logo = ""
            group = ""
            commaing = False
            isTitle = False
            item = ""
            lastchar = ""
            fixed_name = ""
            param = []
            for c in line.split('#EXTINF:')[1]:
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
                if param_name == "tvg-name":
                    name = param_value
                elif param_name == "tvg-logo":
                    logo = re.sub(",", "%2C", param_value)
                elif param_name == "group-title":
                    group = param_value
                elif param_name == "fixed-name" and param_value.upper() == "TRUE":
                    fixed_name = True                    
            song=track(length, group, name, logo, title, None, None, need, fixed_name)
        elif (len(line) != 0):
            # pull song path from all other, non-blank lines
            protocol = line.strip().split('://')[0]
            if protocol not in supports:
                 song=track(None, None, None, None, None, None, None, None, None)
                 continue
            song.path=re.sub(",.*","",line)
            fpath,fname=os.path.split(line)
            if len(fname) >= 32:
                song.fname = fname
            if song.fname != "" and (song.name == "" or song.logo == ""):
                for item in playlist:
                    if item.fname == fname and item.fname != "" and item.name != "":
                        song.name = item.name
                        song.logo = item.logo
                        song.title = re.sub('台$|HD$','', convert(song.title,"zh-cn"))
                        break

            if song.fixed_name:
                    print("fixed_name=True....")

            if song.name == "" or (force_get_name and song.fixed_name != True):
                for item in playlist:
                    if re.sub('台$|HD$|频道$','', convert(song.title,"zh-cn")) == re.sub('台$|HD$|频道$','', convert(item.title,"zh-cn")) \
                        or (item.name != "" and \
                            re.sub('台$|HD$|频道$','', convert(song.title,"zh-cn")) == re.sub('台$|HD$|频道$','', convert(item.name,"zh-cn"))):
                        if item.name != "":
                            song.name = item.name
                        song.logo = item.logo
                        song.title = re.sub('台$|臺$| $','', song.title)
                        break

            if song.name == "" and need:
               song.name = re.sub('台$|HD$', '', convert(song.title,"zh-cn"))
               if song.name[0:5] == 'CCTV-' or song.name[0:5] == 'CCTV_':
                   song.name = song.name[0:4] + song.name[5:]

            if song.logo == "":
               for item in playlist:
                    if song.name == item.name and song.name != "":
                        song.logo = item.logo
                        break

            playlist.append(song)

            # reset the song variable so it doesn't use the same EXTINF more than once
            song=track(None, None, None, None, None, None, None, None, None)

    infile.close()

    return playlist

# for now, just pull the track info and print it onscreen
# get the M3U file path from the first command line argument
def main():
    global force_get_name
    i = 0
    lastop = ''
    reference_m3u = ''
    for op in sys.argv:
        if i == 0:
            i = i + 1
            continue
        if lastop == "-r":
            if os.path.exists(op) and os.path.isfile(op):
                reference_m3u = op
        elif op == "-f":
            force_get_name = True
        elif op != "-r" and op != "-f":
            m3ufile = op
        lastop = op
        i = i + 1

    if i == 1:
        print("Usage: python3 ",sys.argv[0],' [ -f ] [-r <reference m3u file>] input.m3u');
        print("       -f  force get tvg-name from reference m3u file.");
        exit()

    if not os.path.exists(m3ufile) or not os.path.isfile(m3ufile):
        print("Error: source m3u file %s invalid." % m3ufile)
        exit()

    outfile=os.path.join(os.path.split(m3ufile)[0], os.path.split(m3ufile)[1].split(".")[0] + "-new.m3u")
    if reference_m3u != "" and os.path.exists(reference_m3u) and os.path.isfile(reference_m3u):
        print(F'  Parsing reference m3u: {reference_m3u} ...')
        playlist = parsem3u(reference_m3u, False)

    print(F'  Parsing input m3u: {m3ufile} ...')
    playlist = parsem3u(m3ufile, True)
    print(F'  Output new m3u: {outfile} ...')
    out = open(outfile, "w+")
    print("#EXTM3U", end=lineEnds, file=out)
    lastgroup = ""
    for track in playlist:
        if track.need == False:
            continue
        info=F'#EXTINF:{track.length}'
        if track.group != '':
            info = info + F' group-title=\"{track.group}\"'
        if track.name != '' and track.name != track.title:
            info = info + F' tvg-name=\"{track.name}\"'
        if track.logo != '':
            info = info + F' tvg-logo=\"{track.logo}\"'
        if track.fixed_name == True:
            info = info + F' fixed-name=True'
        info = info + F', {track.title}'
        if lastgroup != "" and lastgroup != track.group:
            print("", end=lineEnds, file=out)
        print("%s" % info, end=lineEnds, file=out)
        print("%s" % track.path, end=lineEnds, file=out)
        lastgroup = track.group
    out.close()

if __name__ == '__main__':
    main()
