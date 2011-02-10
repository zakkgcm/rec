#! /usr/bin/env python2
# code copyright (c) Cheeseum 2011
# license: wtfpl v2
# * This program is free software. It comes without any warranty, to
# * the extent permitted by applicable law. You can redistribute it
# * and/or modify it under the terms of the Do What The Fuck You Want
# * To Public License, Version 2, as published by Sam Hocevar. See
# * http://sam.zoy.org/wtfpl/COPYING for more details.

"""rec - Simple, quality screen recording using ffmpeg in python"""

__version__ = '0.1'
__author__ = 'Cheeseum'
__license__ = \
''' 
    rec copyright (c) 2011 Cheeseum released under wtfpl v2 (below)
        
        DO WHAT THE FUCK YOU WANT TO PUBLIC LICENSE
                Version 2, December 2004
    
    Copyright (C) 2004 Sam Hocevar <sam@hocevar.net>
    
    Everyone is permitted to copy and distribute verbatim or modified
    copies of this license document, and changing it is allowed as long
    as the name is changed.
    
    DO WHAT THE FUCK YOU WANT TO PUBLIC LICENSE
    TERMS AND CONDITIONS FOR COPYING, DISTRIBUTION AND MODIFICATION
    
    0. You just DO WHAT THE FUCK YOU WANT TO.
'''

import os, sys, fcntl, time, select
import re, argparse
import subprocess as sub
from Xlib import display

class CamCorder ():
    '''main recording system'''
    
    def __init__ (self):
        self.command = ['ffmpeg', '-y']
        self.dimensions = '640x480'
        self.position = '0,0'
        self.inputs = {}

    def jack_connect (self, src_port, dest_port):
        '''calls jack_connect'''

        ret = sub.call(['jack_connect', src_port, dest_port], stdout=open(os.devnull), stderr=sub.STDOUT)
        if ret != 0:
            print "[jack] Connecting {0} to {1} failed.".format(src_port, dest_port)
        else:
            print "[jack] Connected {0} to {1}.".format(src_port, dest_port)
                    
    def record (self, outfile):
        '''main loop'''
    
        for plug in self.inputs['alsa']:
            self.command.extend(['-f', 'alsa','-i', plug])
        for plug in self.inputs['pulse']:
            self.command.extend(['-f', 'pulse', '-i', plug])
        if len(self.inputs['jack']) > 0:
            self.command.extend(['-f', 'jack', '-i', 'ffmpeg'])
       
        self.command.extend(['-f', 'x11grab', '-r', '60', '-s', self.dimensions, '-i', ':0.0+' + self.position])
        
        self.command.extend(['-vcodec', self.vcodec])
        if self.vpre:
            self.command.extend(['-vpre', self.vpre])

        self.command.extend(['-acodec', self.acodec])
        
        if self.threads:
            self.command.extend(['-threads', self.threads])

        self.command.append(outfile)
        
        try:
            self.ffmpeg = sub.Popen(self.command, stdin=None, stderr=sub.PIPE)
        except OSError:
            print "who someone make error"
            sys.exit(1)
        except ValueError:
            print "Invalid arguments to Popen"
            sys.exit(1)
        
        # ffmpeg writes data out unflushed
        fcntl.fcntl(
            self.ffmpeg.stderr.fileno(),
            fcntl.F_SETFL,
            fcntl.fcntl(self.ffmpeg.stderr.fileno(), fcntl.F_GETFL) | os.O_NONBLOCK,
        )
        
        # [jack @ 0x741500] JACK client registered and activated (rate=48000Hz, buffer_size=256 frames)
        jackre = re.compile(r""".+JACK client registered and activated.+""", re.DOTALL)
        
        # Press [q] to stop encoding
        qencre = re.compile(r""".+Press \[q\] to stop encoding.+""", re.DOTALL)

        # frame=  337 fps= 29 q=-1.0 size=    1135kB time=11.52 bitrate= 806.9kbits/s
        framere = re.compile(r"""\S+\s+(?P<frame>\d+)           # frame
                                 \s\S+\s+(?P<fps>\d+)           # fps
                                 \sq=(?P<q>\S+)                 # q
                                 \s\S+\s+(?P<size>\S+)          # size
                                 \stime=(?P<time>\S+)           # time
                                 \sbitrate=\s*(?P<bitrate>[\d\.]+) # bitrate
                                 """, re.X)

        print "{0} Version {1}".format(os.path.basename(__file__), __version__)
        print ""
        
        # grab ffmpeg output
        while(self.ffmpeg.poll() == None):
            readx = select.select([self.ffmpeg.stderr.fileno()], [], [])[0]
            if readx:
                chunk = self.ffmpeg.stderr.read()
                if chunk == '':
                    next
                
                # pull out recording data
                m = framere.match(chunk)
                if m:
                    sys.stderr.write("frame: {0[frame]} fps: {0[fps]} q: {0[q]} size: {0[size]} time: {0[time]} bitrate: {0[bitrate]} to {1}\r".format(m.groupdict(), outfile))
                # we're probably not recording yet, check for JACK
                m = jackre.match(chunk)
                if m:
                    for plug in self.inputs['jack']:
                        self.jack_connect(plug, 'ffmpeg:input_1')
                    print ""
                
                # to make output prettier
                m = qencre.match(chunk)
                if m:
                    print "Press [q] to stop recording."
                    print ""

            time.sleep(.1)
        
        print ""
        if(self.ffmpeg.returncode == 0):
            print "Recording finished (presumably)."
            sys.exit(0)
        else:
            print "ffmpeg aborted, run the following for more verbose output:"
            print ' '.join(self.command)
            sys.exit(1)

class CameraMan ():
    def main (self):
        '''parse args and begin'''
        
        optparser = argparse.ArgumentParser(description='Record your screen.', epilog='See `ffmpeg -codecs` for a list of available codecs.')

        #optparser.add_argument('-v', '--verbose', action='store_true')
        optparser.add_argument('--version', action='version', version='%(prog)s ' + __version__)
        
        # to be implemented
        #optparser.add_argument('-s', '--select', action='store_true', help="select a window or region to record")
        
        dimgroup = optparser.add_argument_group()
        dimgroup.add_argument('--width',  metavar='width',  default=str(display.Display().screen().width_in_pixels),  type=str, help="specify recording width")
        dimgroup.add_argument('--height', metavar='height', default=str(display.Display().screen().height_in_pixels), type=str, help="specify recording height")
        dimgroup.add_argument('-x', metavar='x', default='0', type=str, help="specify recording x position")
        dimgroup.add_argument('-y', metavar='y', default='0', type=str, help="specify recording y position")

        codecgroup = optparser.add_argument_group()
        codecgroup.add_argument('--vcodec', default='libx264', metavar='codec',  help="force video codec (default: %(default)s)")
        codecgroup.add_argument('--vpre',   default=None,      metavar='preset', help="specify encoder preset (lossless_ultrafast default with libx264)")
        codecgroup.add_argument('--acodec', default='mp2', metavar='codec', help="force audio codec (default: %(default)s)")
        
        audiogroup = optparser.add_argument_group()
        audiogroup.add_argument('--jack',  action='append', dest='jack_inputs',  default=[], metavar='inputs', help="specify inputs from JACK (automatically connected)")
        audiogroup.add_argument('--alsa' , action='append', dest='alsa_inputs',  default=[], metavar='inputs', help="specify inputs from ALSA")
        audiogroup.add_argument('--pulse', action='append', dest='pulse_inputs', default=[], metavar='inputs', help="specify inputs from PulseAudio")

        optparser.add_argument('--threads', default='0', help="number of threads to use (0 is a sane default) (default: %(default)s)")
        optparser.add_argument('--no-threads', action='store_false', dest='use_threads', help="disable threads")
        optparser.add_argument('outfile', metavar='file')
        
        args = optparser.parse_args()
        
        camera = CamCorder()
        camera.inputs = {'alsa': args.alsa_inputs, 'jack': args.jack_inputs, 'pulse': args.pulse_inputs}

        # in the future these may be a dict of options
        camera.vcodec = args.vcodec
        camera.vpre = args.vpre
        if args.vcodec == 'libx264'  and not args.vpre:
            camera.vpre = 'lossless_ultrafast'
        
        camera.acodec = args.acodec

        camera.dimensions = args.width + 'x' + args.height
        camera.position = args.x + ',' + args.y
        
        if args.use_threads:
            camera.threads = args.threads

        camera.record(args.outfile)

if __name__ == "__main__":
    try:
        CameraMan().main()
    except KeyboardInterrupt:
        pass
