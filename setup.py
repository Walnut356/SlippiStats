import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    author="Walnut",
    author_email="walnut356@gmail.com",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    description="Stats library for SSBM replay files",
    install_requires=['py-ubjson', 'termcolor'],
    long_description=long_description,
    long_description_content_type="text/markdown",
    name="py-slippi-stats",
    packages=setuptools.find_packages(),
    python_requires='>=3.10',
    tests_require=['mypy', 'types-termcolor'],
    url="https://github.com/Walnut356/py-slippi-stats",
    version="0.1.0",
)
