# OMEMO Plugin for Gajim

Experimental plugin that adds support for the [OMEMO
Encryption](http://conversations.im/omemo) to [Gajim](https://gajim.org/).

**DO NOT rely on this plugin to protect sensitive information!** 

## Dependencies
All dependencies can be installed with `pip`. (Depending on your setup you might
want to use `pip2` as Gajim is using python2.7)

* python-axolotl

## Installation
Clone the git repository into Gajim's plugin directory.

```shell
mkdir ~/.local/share/gajim/plugins -p
cd ~/.local/share/gajim/plugins
git clone git@github.com:kalkin/gajim-omemo.git
```

## Running
Enable *OMEMO Multi-End Message and Object Encryption* in the Plugin-Manager.
Before exchanging encrypted messages with a contact you have to hit the *Get
Device Keys* button. (Repeat that if you or your contact get new devices.)

Currently the plugin has no user interface for confirming the own and foreign
device keys.  It uses trust on first use. This will be added in near future.

## Debugging
To see OMEMO related debug output start Gajim with the parameter `-l
gajim.plugin_system.omemo=DEBUG`.


