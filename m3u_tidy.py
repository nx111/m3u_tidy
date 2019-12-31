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
        skip_line = False
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
        elif (len(line.strip()) != 0):
            # pull song path from all other, non-blank lines
            protocol = line.strip().split('://')[0]
            if protocol not in supports:
                 song=track(None, None, None, None, None, None, None, None, None)
                 continue
            song.path=re.sub(",.*","",line)
            fpath,fname=os.path.split(line)
            if len(fname) >= 32:
                song.fname = fname
            else:
                song.fname = ""

            # skip duplicate list item
            for item in playlist:
                if (item.title != "" and \
                       re.sub('台$|HD$|频道$','', convert(song.title,"zh-cn")) \
                       == re.sub('台$|HD$|频道$','', convert(item.title,"zh-cn"))) \
                   or (item.name != "" and \
                       re.sub('台$|HD$|频道$','', convert(song.title,"zh-cn")) \
                        == re.sub('台$|HD$|频道$','', convert(item.name,"zh-cn"))):
                     if item.path == song.path and item.group == song.group and item.need == song.need:
                         song=track(None, None, None, None, None, None, None, None, None)
                         skip_line = True
                         break
            if skip_line:
                continue

            if song.fname != "" and (song.name == "" or song.logo == ""):
                for item in playlist:
                    if item.fname == fname and item.fname != "" and item.name != "":
                        if item.name != "":
                            song.name = item.name
                        if item.logo != "":
                            song.logo = item.logo
                        song.title = re.sub('台$|HD$','', convert(song.title,"zh-cn"))
                        break

            if song.name == "" or (force_get_name and song.fixed_name != True):
                for item in playlist:
                    if re.sub('台$|HD$|频道$','', convert(song.title,"zh-cn")) == re.sub('台$|HD$|频道$','', convert(item.title,"zh-cn")) \
                        or (item.name != "" and \
                            re.sub('台$|HD$|频道$','', convert(song.title,"zh-cn")) == re.sub('台$|HD$|频道$','', convert(item.name,"zh-cn"))):
                        if item.name != "":
                            song.name = item.name
                        if item.logo != "":
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
        else:
            song=track(None, None, None, None, None, None, None, None, None)

    infile.close()

    return playlist

def parsetxt(infile, need):
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
    if len(line) >= 7 and line[0:7] == b'#EXTM3U':
       print(F'{infile} could be m3u file, not txt format tvlist.')
       return
    if need and line.splitlines(True)[0][-2:-1] == b'\r':
        lineEnds='\r\n'

    infile.close()

    infile = open(ifile, 'r')
    # initialize playlist variables before reading file
    song=track(None, None, None, None, None, None, None, None, None)
    group = ""
    for line in infile:
        line=line.strip()
        if line != "":
            # pull length and title from #EXTINF line
            title = ""
            param = []
            if line.split(',')[1].strip() == '#genre#':
                group = line.split(',')[0].strip()
                continue

            skipme = False
            title = line.split(',')[0].strip()
            path = line.split(',')[1].strip()

            urls = path.split('#')
            path = ''
            i = 0
            for item in urls:
                j = 0
                foundme = False
                simple_item = re.sub('\$.*|\.flv$|\.m3u8$', '', item).strip()
                while j < i:
                    if simple_item == re.sub('\$.*|\.flv$|\.m3u8$', '', urls[j]).strip():
                        foundme = True
                        if os.path.splitext(re.sub('\$.*', '', item))[1] == '.m3u8' \
                               and  os.path.splitext(re.sub('\$.*', '', urls[j]))[1] == '.flv':
                            label = ''
                            if len(urls[j].split('\$')) > 1:
                                label = '$' + urls[j].split('\$')[1]
                            urls[j] = os.path.splitext(re.sub('\$.*', '', urls[j]))[0] + '.m3u8' + label
                            item = ''
                        break
                    j += 1
                if foundme:
                    i += 1
                    continue
                i += 1
                for list_item in playlist:
                    if re.sub('台$| ', '', convert(title, "zh-cn")) == re.sub('台$| ', '', convert(list_item.title, "zh-cn")):
                        foundit = False
                        url_items = list_item.path.split("#")
                        jj = 0
                        for url_item in url_items:
                            simple_url_item = re.sub('\$.*|\.flv$|\.m3u8$', '', url_item).strip()
                            if simple_url_item == simple_item:
                                foundit = True
                                if os.path.splitext(re.sub('\$.*', '', item))[1] == '.m3u8' \
                                       and  os.path.splitext(re.sub('\$.*', '', url_items[jj]))[1] == '.flv':
                                    label = ''
                                    if len(url_items[jj].split('\$')) > 1:
                                         label = '$' + url_items[jj].split('\$')[1]
                                         url_items[jj] = os.path.splitext(re.sub('\$.*', '', url_items[jj]))[0] + '.m3u8' + label
                                jj += 1
                                break
                            jj += 1
                        list_item.path = ''
                        for url_item in url_items:
                            if list_item.path != '':
                                list_item.path += '#'
                            list_item.path += url_item

                        if foundit == False:
                            if list_item.need:
                                if list_item.group == group:
                                    skipme = True
                                    list_item.path += "#" + item.strip()
                                else:
                                    item = list_item.path + "#" + item.strip()
                            else:
                                item = item.strip() + "#" + list_item.path

            path = ''
            for item in urls:
                if item != '':
                    if path != "":
                       path += '#'
                    path += item
            title = re.sub('台$', '', convert(title, "zh-cn"))
            song=track(0, group, None, None, title, path, None, need, None)

            if not skipme:
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
    reference_file = ''
    input_file = ''
    for op in sys.argv:
        if i == 0:
            i = i + 1
            continue
        if lastop == "-r":
            if os.path.exists(op) and os.path.isfile(op):
                reference_file = os.path.realpath(op)
        elif op == "-f":
            force_get_name = True
        elif op != "-r" and op != "-f":
            input_file = os.path.realpath(op)
        lastop = op
        i = i + 1

    if i == 1:
        print("Usage: python3 ",sys.argv[0],' [ -f ] [-r <reference file>] input_file');
        print("       -f  force get tvg-name from reference file.");
        print("")
        print("           reference file and input file can be m3u or txt file.");
        exit()

    if not os.path.exists(input_file) or not os.path.isfile(input_file):
        print("Error: source m3u file %s invalid." % input_file)
        exit()

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
    print(F'  Output new file:        {outfile} ...')
    out = open(outfile, "w+")

    if os.path.splitext(outfile)[1] == '.m3u':
        print("#EXTM3U", end=lineEnds, file=out)
        lastgroup = ""
        for track in playlist:
            if track == None or track.need == False:
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
    elif os.path.splitext(outfile)[1] == '.txt':
        lastgroup = ""
        for track in playlist:
            if track == None or track.need == False:
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
