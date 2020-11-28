
output_dir = dist
ifeq ($(OS),Windows_NT)
	RM := rmdir /S /Q
else
	RM := rm -rf
endif

wheel:
	make cleandir
	python setup.py sdist --formats=gztar bdist_wheel

cleandir:
	-$(RM) $(output_dir)

upload:
	twine upload dist/*.tar.gz dist/*.whl