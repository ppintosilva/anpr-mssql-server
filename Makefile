red:=$(shell tput setaf 1)
blue:=$(shell tput setaf 4)
green:=$(shell tput setaf 2)
reset:=$(shell tput sgr0)

pip : /usr/bin/python2.7
	$(info $(blue)Installing local pip for current user [$(USER)]$(reset))
	@/usr/bin/python2.7 -m pip install --user --upgrade pip
	
virtualenv : /usr/bin/python2.7
	$(info $(blue)Installing pip for current user [$(USER)]$(reset))
	@/usr/bin/python2.7 -m pip install --user virtualenv
	@/usr/bin/python2.7 -m virtualenv ENV

dependencies : ENV/bin/pip2.7 requirements.txt
	$(info $(blue)Installing pip dependencies defined in requirements.txt in virtualenv$(reset))
	@ENV/bin/pip2.7 install -r requirements.txt

test: server.py
	$(info $(blue)Testing installation$(reset))
	@ENV/bin/python server.py --help

install : pip virtualenv dependencies test
	
clean :
	$(info $(red)Removing virtualenv in directory 'ENV'$(reset))
	@rm -rf ENV
