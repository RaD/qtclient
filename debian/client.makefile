VERSION=0.4.1
PROJECT=advisor-client
PROJECT_EGG=advisor_client-$(VERSION).egg-info

clean:
	rm -rf *.py[co] *~

install:
	python setup.py install --prefix=$(DESTDIR)

uninstall:
	cd $(DESTDIR)/lib/python2.6/site-packages/; \
	rm -rf $(PROJECT); \
	rm -r $(PROJECT_EGG); \
	cd -
