import setuptools

with open("README.md", "r", encoding="utf8") as readme_file:
    long_description = readme_file.read()

setuptools.setup(
    name="pcbdl",
    version="0.1.1",
    author="Google LLC",
    description="A programming way to design schematics.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    license="Apache-2.0",
    url="https://github.com/google/pcbdl",
    packages=setuptools.find_packages(),
    keywords=["eda", "hdl", "electronics", "netlist", "hardware", "schematics"],
    install_requires=["pygments"],
    classifiers=[
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Topic :: Scientific/Engineering :: Electronic Design Automation (EDA)",
        "Topic :: System :: Hardware",
    ],
)
