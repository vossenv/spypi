
output_dir = dist
ifeq ($(OS),Windows_NT)
	RM := rm -r -f
else
	RM := rm -rf
endif

wheel:
	make cleandir
	python setup.py bdist_wheel

cleandir:
	-$(RM) $(output_dir)

upload:
	twine upload -r dev dist/*

deploy:
	make wheel
	make upload