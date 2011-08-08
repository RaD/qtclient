PROJECT=advisor-client
VERSION=0.4.1

BASEDIR=$(shell pwd)
BUILD=$(BASEDIR)/build
DST=$(BUILD)/client
LCL=locale/ru/LC_MESSAGES

all:
	echo "Usage: make dist"

clean:
	rm -rf ./build

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
	cd $(BASEDIR)/build/dist; \
    cp $(PROJECT)-$(VERSION).tar.gz $(PROJECT)_$(VERSION).orig.tar.gz; \
	tar xzf $(PROJECT)-$(VERSION).tar.gz; \
	cd -

	dch -i

	cp -r $(BASEDIR)/debian $(BASEDIR)/build/dist/$(PROJECT)-$(VERSION)/

	cd $(BASEDIR)/build/dist/$(PROJECT)-$(VERSION); \
	debuild -k4A43B8D0; \
	cd -
