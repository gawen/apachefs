# apachefs

``apachefs`` is a Python script which makes you able to locally mount a file tree served by Apache (like the [Heanet public mirror](http://ftp.heanet.ie/pub/)). It's the default apache's behavior when it has to serve a file tree without any ``index.html`` file. The filesystem is obviously read-only.

Works on Linux, MacOS X, FreeBSD.

## How to use it ?

First get the code of this repository.

    $ git clone http://github.com/Gawen/apachefs
    $ cd apachefs

Before actually using the script, you will first require to install ``fusepy`` and ``BeautifulSoup``.

    $ easy_install fusepy beautifulsoup

The script to use is named ``apachefs.py``.

    $ ./apachefs.py --help
    Usage: apachefs.py [options]

    Options:
      -h, --help        show this help message and exit
      -v, --verbose     
      -f, --foreground  

``-v`` sets the log's level to debug. ``-f`` keeps the process to foreground.

For example, let's mount the Ubuntu's heanet mirror: [http://ftp.heanet.ie/pub/ubuntu-cdimage/releases/](http://ftp.heanet.ie/pub/ubuntu-cdimage/releases/).

    $ mkdir heanet
    $ ./apachefs.py http://ftp.heanet.ie/pub/ubuntu-cdimage/releases/
    $ cd heanet
    $ ls
    10.04
    10.04.1
    10.04.2
    10.04.3
    10.04.4
    11.10
    12.04
    12.04.1
    12.10
    8.04
    8.04.1
    8.04.3
    8.04.4
    hardy
    lucid
    oneiric
    precise
    quantal
    $

The ``cd heanet`` and ``ls`` operation could take a while, because it requires the script to do a ``HEAD`` request for each of the files in the directory to have the file meta-attributes.

To un-mount the filesystem, just type.
    
    $ fusermount -u heapnet

And you're done.

## License

The code is under MIT license.

## Links

* fusepy repository: [https://github.com/terencehonles/fusepy](https://github.com/terencehonles/fusepy)
* BeautifulSoup website: [http://www.crummy.com/software/BeautifulSoup/](http://www.crummy.com/software/BeautifulSoup/)
* Heapnet public mirror, an URL compatible with ``apachefs``: [http://ftp.heanet.ie/pub/](http://ftp.heanet.ie/pub/)

