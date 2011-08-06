PROJECT=advisor-client
VERSION=0.4.1

BASEDIR=$(shell pwd)
BUILD=$(BASEDIR)/build
DST=$(BUILD)/client
DEBINFO=$(BASEDIR)/debian
LCL=locale/ru/LC_MESSAGES
DEBBASE=$(BASEDIR)/debianize
PACKDIR=$(DEBBASE)/$(PROJECT)-$(VERSION)

all:
	echo "Usage: make dist"

clean:
	rm -rf ./build ./debianize

build: dist debianize

dist:
	mkdir -p $(DST) $(DST)/$(LCL) $(DST)/uis $(DST)/dialogs
	cd ./src; make pomo; cd -
	cp ./src/*.py ./src/*.css $(DST)/
	cp ./src/uis/*.ui $(DST)/uis/
	cp ./src/dialogs/*.py $(DST)/dialogs/
	cp ./src/$(LCL)/*mo $(DST)/$(LCL)/
	cp ./package/* $(BUILD)/

	cd $(BUILD); python setup.py sdist; cd -

debianize:
	mkdir -p $(PACKDIR)/debian/

	cp $(DEBINFO)/client.makefile $(PACKDIR)/Makefile
	cp $(DEBINFO)/rules $(PACKDIR)/debian/

	sed -e "s/<PROJECT>/$(PROJECT)/" \
	    -e "s/<FULLNAME>/$(DEBFULLNAME)/" \
	    -e "s/<EMAIL>/<$(DEBEMAIL)>/" \
	    < $(DEBINFO)/control > $(PACKDIR)/debian/control
	sed -e "s/<DATE>/`LANG=C date`/" \
	    -e "s/<FULLNAME>/$(DEBFULLNAME)/" \
	    -e "s/<EMAIL>/<$(DEBEMAIL)>/" \
	    < $(DEBINFO)/copyright > $(PACKDIR)/debian/copyright

	cd $(DEBBASE); tar xzf $(BUILD)/dist/$(PROJECT)-$(VERSION).tar.gz; cd -
	cd $(PACKDIR)/; \
	test -f debian/changelog || debchange --create --package $(PROJECT) -v $(VERSION); \
	test -f debian/compat || (test -f /etc/debian_version && echo "7" || echo "6") >> ./debian/compat; \
	cd -

	echo "Now you're ready to build the package."
	echo "Just do:"
	echo "    cd $(PACKDIR)"
	echo "    debuild -k<YOUR_PGP_KEY>"

