SHELL=/bin/bash

update-contributors:
	@echo "# this file was auto generated - do not edit directly" > CONTRIBUTORS && \
	@git shortlog --summary --numbered --email >> CONTRIBUTORS