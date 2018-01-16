Sources:
* http://stackoverflow.com/questions/38393054/installing-python-3-5-via-apt-get
* http://stackoverflow.com/questions/38249961/install-pip-for-python-3-5

```
  $ sudo apt-get install libssl-dev openssl
  $ wget https://www.python.org/ftp/python/3.5.0/Python-3.5.0.tgz
  $ tar xzvf Python-3.5.0.tgz
  $ cd Python-3.5.0
  $ ./configure
  $ make
  $ sudo make install
  $ sudo apt-get install python3-setuptools
  $ sudo python3.5 /usr/local/lib/python3.5/site-packages/easy_install.py pip
  $ sudo pip3.5 install slackclient
  $ sudo pip3.5 install mandrill
```
