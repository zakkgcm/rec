#_rec_ Lightweight desktop recorder
_rec_ is a lightweight python desktop recorder
it merely wraps around _ffmpeg_ and _jack_connect_ to streamline and simplify recording
currently there is no GUI interface

## Goals
* Lightweight
* Supportive of "special cases" (as in JACK)
* Simple to use

## Dependencies
* python 2.x
* python-xlib
* ffmpeg
* libx264 *
* jack *
* alsa *
* pulse-audio *

*optional unless you intend to use those

## Install
right now there's no install script
all it would do is `mv rec.py /usr/bin/rec` anyway

## Usage
rec --jack system:some_port --acodec libmp3lame out.avi

## Misc
#### Whining
_"what hte fux is dis: Xlib.protocol.request.QueryExtension???/ y did u make it do dis?//"_
python-xlib bug, supposedly fixed already

#### Future Plans
window and screen region selection
more support for options
simple GUI that hides in a systray icon
