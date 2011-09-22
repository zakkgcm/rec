#! /usr/bin/env python2
# code copyright (c) Cheeseum 2011
# license: wtfpl v2
# * This program is free software. It comes without any warranty, to
# * the extent permitted by applicable law. You can redistribute it
# * and/or modify it under the terms of the Do What The Fuck You Want
# * To Public License, Version 2, as published by Sam Hocevar. See
# * http://sam.zoy.org/wtfpl/COPYING for more details.

"""rec - Simple, quality screen recording using ffmpeg in python"""

__version__ = '0.4'
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
import tempfile
import re, argparse
import subprocess as sub
from Xlib import X, Xcursorfont, display
from Xlib import error as Xerror

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
            
    def jack_capture (self, filepath):
        ''' calls jack_capture, returns a process handle'''

        # TODO: implement configurable format
        command = ['jack_capture', '-f', 'flac', '-dm', filepath]
        try:
            process = sub.Popen(command, stdout=open(os.devnull), stderr=sub.STDOUT, stdin=sub.PIPE)
        except OSError:
            print "jack_capture: who someone make error"
            sys.exit(1)
        except ValueError:
            print "Invalid arguments to Popen"
            sys.exit(1)
        
        return process

    def record (self, outfile):
        '''main loop'''
        
        if self.inputs['alsa'] or self.inputs['pulse'] or self.inputs['jack']:
            self.command.extend(['-ac', self.achannels])
            self.command.extend(['-ar', self.arate])

            for plug in self.inputs['alsa']:
                self.command.extend(['-f', 'alsa','-i', plug])
            for plug in self.inputs['pulse']:
                self.command.extend(['-f', 'pulse', '-i', plug])
            if not self.use_jack_capture and len(self.inputs['jack']) > 0:
                self.command.extend(['-f', 'jack', '-i', 'ffmpeg'])
            
            self.command.extend(['-acodec', self.acodec])
    
        self.command.extend(['-f', 'x11grab'])
        
        if self.rate < 0:
            self.rate = 60

        self.command.extend(['-r', self.rate])
        self.command.extend(['-s', self.dimensions, '-i', ':0.0+' + self.position])
       
        self.command.extend(['-vcodec', self.vcodec])
        if self.vpre:
            self.command.extend(['-vpre', self.vpre])
        if int(self.gop) > 0:
            self.command.extend(['-g', self.gop])

        self.command.extend(['-sameq'])

        if self.threads:
            self.command.extend(['-threads', self.threads])
        
        # Create a tmp file for jack_capture's audio and the recorded video
        if self.use_jack_capture:
            try:
                f, video_tmp = tempfile.mkstemp(suffix=os.path.splitext(outfile)[1], dir=os.getcwd(), prefix='rec')
                self.command.append(video_tmp)
                os.close(f)

                f, audio_tmp = tempfile.mkstemp(suffix='.flac', dir=os.getcwd(), prefix='rec')
                jack_capture = self.jack_capture(audio_tmp)
                os.close(f)
                del f
            except Exception as e:
                print "Problem making temp files: {0}".format(e)
        else:
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
        qencre = re.compile(r""".+Press \[q\] to stop.+""", re.DOTALL)

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
                if m and not self.use_jack_capture:
                    for plug in self.inputs['jack']:
                        self.jack_connect(plug, 'ffmpeg:input_1')
                    print ""
                
                # to make output prettier
                m = qencre.match(chunk)
                if m:
                    print "Recording {0} area at position {1}.".format(self.dimensions, self.position)
                    print "Press [q] to stop recording."
                    print ""

            time.sleep(.1)
        
        if(self.ffmpeg.returncode == 0):
            print "Recording finished (presumably)."
            
            # with jack_capture we need to do a combine the audio stream with the video at the end
            if self.use_jack_capture:
                jack_capture.terminate()

                print "Combining jack_capture audio with recorded video to {0}".format(outfile)
                print "Please wait warmly."

                combine_command = ['ffmpeg', '-y', '-i', audio_tmp, '-i', video_tmp, '-sameq']
                if self.threads:
                    combine_command.extend(['-threads', self.threads])

                ret = sub.call(combine_command, stdout=open(os.devnull), stderr=sub.STDOUT)
                if ret != 0:
                    print "Fail!"
                    print "Something went wrong when muxing in the audio!"
                    print "Your jack_connect audio is here: {0}".format(audio_tmp)
                    print "Your recorded video is here: {0}".format(video_tmp)
                else:
                    print "Done!"
                    print ""

                    os.remove(audio_tmp)
                    os.remove(video_tmp)
                    
            sys.exit(0)
        else:
            print "ffmpeg aborted, run the following for more verbose output:"
            print ' '.join(self.command)
            sys.exit(1)

class CameraMan ():
    def __init__ (self):
        self.d = display.Display()
        self.screen = self.d.screen()
    
    # TODO: compress this entire hunk of code down
    # TODO: more thorough error handling

    def select_area (self):
        '''select a rectangular region or window'''
        '''based on Tom Gilbert's scrot code'''
        
        rect = Rectangle()
        outrect = Rectangle()
        gc = self.screen.root.create_gc(
                foreground = self.screen.white_pixel,
                background = self.screen.black_pixel,
                function = X.GXxor,
                plane_mask = self.screen.white_pixel ^ self.screen.black_pixel,
                subwindow_mode = X.IncludeInferiors
            )

        cursor_font = self.d.open_font('cursor')
        cursor = cursor_font.create_glyph_cursor(cursor_font, Xcursorfont.crosshair, Xcursorfont.crosshair + 1,
                        (0, 0, 0), (0xffff, 0xffff, 0xffff)
                 )
        
        # grab pointer and keyboard
        try:
            self.screen.root.grab_pointer(
                owner_events = False,
                event_mask = X.ButtonMotionMask | X.ButtonPressMask | X.ButtonReleaseMask,
                pointer_mode = X.GrabModeAsync,
                keyboard_mode = X.GrabModeAsync,
                confine_to = self.screen.root,
                cursor = cursor,
                time = X.CurrentTime
             )
        except Exception as e:
            print "Couldn't grab pointer: {0}".format(e)
            sys.exit(1)

        try: 
            ret = self.screen.root.grab_keyboard(
                owner_events = False,
                pointer_mode = X.GrabModeAsync,
                keyboard_mode = X.GrabModeAsync,
                time = X.CurrentTime
            )
        except Exception as e:
            print "Couldn't grab keyboard: {0}".format(e)
            sys.exit(1)
        
        done = False
        grabbed = True
        button_pressed = False
        # grab events
        while True: 
            while not done and self.d.pending_events():
                ev = self.d.next_event()
                if ev.type == X.MotionNotify and button_pressed:
                    if (rect.width):
                        self.screen.root.rectangle(gc, rect.x, rect.y, rect.width, rect.height)
                    else:
                        self.d.change_active_pointer_grab(
                            event_mask = X.ButtonMotionMask | X.ButtonReleaseMask,
                            cursor = cursor,
                            time = X.CurrentTime
                        )
                        
                    rect.x = outrect.x
                    rect.y = outrect.y
                    rect.width  = ev.event_x - rect.x
                    rect.height = ev.event_y - rect.y

                    if rect.width < 0:
                        rect.x += rect.width
                        rect.width = 0 - rect.width
                    if rect.height < 0:
                        rect.y += rect.height
                        rect.height = 0 - rect.height
                    
                    self.screen.root.rectangle(gc, rect.x, rect.y, rect.width, rect.height)
                    self.d.flush()
                
                elif ev.type == X.ButtonPress:
                    button_pressed = True
                    outrect.x = ev.event_x
                    outrect.y = ev.event_y

                    # attempt to get a window
                    target = self.get_window(ev.child, ev.event_x, ev.event_y)
                    if target == None:
                        target = self.screen.root

                elif ev.type == X.ButtonRelease:
                    done = True
                elif ev.type == X.KeyPress:
                    print "Key was pressed, exiting..."
                    done = True
                    grabbed = False
                elif ev.type == X.KeyRelease:
                    pass
                else:
                    pass
            
            if done: break;
        # end grab events

        if rect.width:
            self.screen.root.rectangle(gc, rect.x, rect.y, rect.width, rect.height)
            self.d.flush()

        self.d.ungrab_pointer(X.CurrentTime)
        self.d.ungrab_keyboard(X.CurrentTime)
        gc.free()
        cursor.free()
        self.d.sync()
        
        if grabbed:
            if rect.width > 5:
                # rectangle was drawn
                outrect.width  = ev.event_x - outrect.x
                outrect.height = ev.event_y - outrect.y
                
                if outrect.width < 0:
                    outrect.x += outrect.width
                    outrect.width = 0 - outrect.width
                if outrect.height < 0:
                    outrect.y += outrect.height
                    outrect.height = 0 - outrect.height
            
            else:
                # window was clicked
                if target != self.screen.root:
                    status = target.get_geometry()

                    # find wm frame
                    while True:
                        s = target.query_tree()
                        if s.parent == None or s.parent == s.root:
                            break
                        target = s.parent
                    
                    # get client win
                    target = self.get_client_window(target)
                    target.raise_window()
                
                attr = target.get_attributes()
                if not attr or attr.map_state != X.IsViewable:
                    return None

                targetgeo = target.get_geometry()
                outrect.width  = targetgeo.width
                outrect.height = targetgeo.height
                
                r = self.screen.root.translate_coords(target, 0, 0)
                outrect.x = r.x
                outrect.y = r.y
            
            # clip rectangle
            if outrect.x < 0:
                outrect.width += outrect.x
                outrect.x = 0
            if outrect.y < 0:
                outrect.height += outrect.y
                outrect.y = 0
            if (outrect.x + outrect.width) > self.screen.width_in_pixels:
                outrect.w = self.screen.width_in_pixels - outrect.x
            if (outrect.y + outrect.height) > self.screen.height_in_pixels:
                outrect.height = self.screen.height_in_pixels - outrect.y
            
            # some encoders (aka libx264) cannot into odd sizes
            if (outrect.width % 2) != 0:
                if (outrect.width + 1) > self.screen.width_in_pixels:
                    outrect.width -= 1
                else:
                    outrect.width +=1
            if (outrect.height % 2) != 0:
                if (outrect.height + 1) > self.screen.height_in_pixels:
                    outrect.height -= 1
                else:
                    outrect.height +=1

            return outrect
        return None
            
    def get_window (self, window, x, y):
        source = self.screen.root
        target = window
        if window == X.NONE:
            window = self.screen.root
                 
        while True:
            s = source.translate_coords(window, x, y)
            target = s.child

            if s == X.NONE:
                break
            if target == X.NONE:
                break;
            
            source = window
            window = s.child
            x = s.x
            y = s.y
        
        if target == X.NONE:
            target = window
        return target
    
    def get_client_window (self, target):
        prop = self.d.intern_atom("WM_STATE", True)
        if prop == X.NONE:
            return target
        status = target.get_property(prop, X.AnyPropertyType, 0, 0)
        if status != None and status.property_type != X.NONE:
            return target
        client = self.get_window_from_property(target, prop)
        if client == None:
            return target
        return client
    
    def get_window_from_property (self, window, prop):
        child = None
        s = window.query_tree()
        if s == None:
            return None
        for c in s.children:
            if child != None:
                break

            data = c.get_property(prop, X.AnyPropertyType, 0, 0)
            if data != None and data.property_type != X.NONE:
                child = c
        for c in s.children:
            if child != None:
                break
            child = self.get_window_from_property(c, prop)
        return child

    def main (self):
        '''parse args and begin'''
        
        optparser = argparse.ArgumentParser(description='Record your screen.', epilog='See `ffmpeg -codecs` for a list of available codecs.')

        #optparser.add_argument('-v', '--verbose', action='store_true')
        optparser.add_argument('--version', action='version', version='%(prog)s ' + __version__)
        
        # to be implemented
        optparser.add_argument('-s', '--select', action='store_true', help="select a window or region to record")
        
        framegroup = optparser.add_argument_group()
        framegroup.add_argument('-r', '--rate', metavar='framerate', default='60', type=str, help="framerate of capture (default: %(default)s)")
        framegroup.add_argument('-g', '--gop', metavar='gop', default='-1', type=str, help="set GOP size (number of smoothing frames)")
        
        dimgroup = optparser.add_argument_group(description="These arguments are overriden by -s/--select.")
        dimgroup.add_argument('--width',  metavar='width',  default=str(self.screen.width_in_pixels),  type=str, help="specify recording width (default: screen width)")
        dimgroup.add_argument('--height', metavar='height', default=str(self.screen.height_in_pixels), type=str, help="specify recording height (default: screen height)")
        dimgroup.add_argument('-x', metavar='x', default='0', type=str, help="specify recording x position (default: 0)")
        dimgroup.add_argument('-y', metavar='y', default='0', type=str, help="specify recording y position (default: 0)")

        codecgroup = optparser.add_argument_group()
        codecgroup.add_argument('--vcodec', default='libx264', metavar='codec',  help="force video codec (default: %(default)s)")
        codecgroup.add_argument('--vpre',   default=None,      metavar='preset', help="specify encoder preset (lossless_ultrafast default with libx264)")
        codecgroup.add_argument('--acodec', default='mp2', metavar='acodec', help="force audio codec (default: %(default)s)")
        codecgroup.add_argument('-ar', '--arate', default='48000', metavar='arate', help="force audio rate (default: %(default)s)")
        codecgroup.add_argument('-ac', '--achannels', default='1', metavar='achannels', help="force audio channels (default: %(default)s)")
 
        audiogroup = optparser.add_argument_group()
        audiogroup.add_argument('--jack-capture', action='store_true', help="use jack_capture to capture jack audio (disables jack inputs)")
        audiogroup.add_argument('--jack',  action='append', dest='jack_inputs',  default=[], metavar='inputs', help="specify inputs from JACK (automatically connected)")
        audiogroup.add_argument('--alsa' , action='append', dest='alsa_inputs',  default=[], metavar='inputs', help="specify inputs from ALSA")
        audiogroup.add_argument('--pulse', action='append', dest='pulse_inputs', default=[], metavar='inputs', help="specify inputs from PulseAudio")

        optparser.add_argument('--threads', default='0', help="number of threads to use (default: guess)")
        optparser.add_argument('--no-threads', action='store_false', dest='use_threads', help="disable threads")
        optparser.add_argument('outfile', metavar='file')
        
        args = optparser.parse_args()
        
        camera = CamCorder()
        camera.use_jack_capture = args.jack_capture
        camera.inputs = {'alsa': args.alsa_inputs, 'jack': args.jack_inputs, 'pulse': args.pulse_inputs}

        # in the future these may be a dict of options
        camera.vcodec = args.vcodec
        camera.vpre = args.vpre
        if args.vcodec == 'libx264'  and not args.vpre:
            camera.vpre = 'lossless_ultrafast'

        camera.acodec = args.acodec
        camera.arate = args.arate
        camera.achannels = args.achannels
        camera.rate = args.rate
        camera.gop = args.gop

        rect = Rectangle(args.x, args.y, args.width, args.height)  
        if args.select:
            rect = self.select_area()
            if not rect:
                print "Error grabbing area!"
                sys.exit(1)
        
        camera.dimensions = str(rect.width) + 'x' + str(rect.height)
        camera.position = str(rect.x) + ',' + str(rect.y)
        
        if args.use_threads:
            camera.threads = args.threads
       
        # overwrite confirmation
        if os.path.isfile(args.outfile):
            ans = raw_input("{0} exists! Overwrite? [y/n]: ".format(args.outfile))
            if ans != 'y' or ans != 'Y':
                sys.exit(0)

        camera.record(args.outfile)

class Rectangle:
    '''simple rectangle with width, height, x, and y'''

    def __init__ (self, x=0, y=0, width=0, height=0):
        self.x, self.y = x, y
        self.width, self.height = width, height

    def __repr__(self):
        return "x: {0} y: {1} w: {2} h: {3}".format(self.x, self.y, self.width, self.height)

if __name__ == "__main__":
    try:
        CameraMan().main()
    except KeyboardInterrupt:
        pass
