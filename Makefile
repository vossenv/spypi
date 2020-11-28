
output_dir = dist
ifeq ($(OS),Windows_NT)
	RM := rmdir /S /Q
else
	RM := rm -rf
endif

cleandir:
	-$(RM) $(output_dir)

standalone:
	make cleandir
	pyinstaller --clean --noconfirm adobe_serial_tool.spec

wheel:
	make cleandir
	python setup.py sdist --formats=gztar bdist_wheel

upload:
	twine upload dist/*.tar.gz dist/*.whl