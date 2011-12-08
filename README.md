#_rec_ Lightweight Desktop Recorder
_rec_ is a lightweight python desktop recorder  
it merely wraps around _ffmpeg_, _jack_capture_, and _jack_connect_ to streamline and simplify recording  
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
* jack_capture *

*optional unless you intend to use those

## Install
right now there's no install script, all it would do is `mv rec.py /usr/bin/rec` anyway

## Usage
`rec --jack system:some_port --acodec libmp3lame out.avi`  
`rec -s --jack-capture -g 300 out.avi`


## Misc
#### Name Change
currently there exists already a "rec", it's part of _sox_ which is a dependency of _mlt_ which in turn is needed by _kdenlive_  
so with that this is probably going to need to be called something else, leaning towards _screc_ right now

#### Future Plans
* more support for options
* simple GUI that hides in a systray icon
