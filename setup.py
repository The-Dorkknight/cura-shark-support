# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""pip packaging for the command line tool. The Cura plugin is installed with install.py instead."""
from setuptools import setup

setup(
    name="shark-support",
    version="0.2.1.dev0",
    description="Shark-fin supports for flat tilted overhangs (WORK IN PROGRESS)",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="Matthew Armstrong",
    author_email="The-Dorkknight@users.noreply.github.com",
    url="https://github.com/The-Dorkknight/cura-shark-support",
    license="PolyForm-Noncommercial-1.0.0",
    packages=["SharkSupport"],
    package_data={"SharkSupport": ["plugin.json", "qml/*.qml"]},
    py_modules=["shark_cli"],
    install_requires=["numpy>=1.21"],
    python_requires=">=3.8",
    entry_points={"console_scripts": ["shark-support=shark_cli:main"]},
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "License :: Other/Proprietary License",
        "Programming Language :: Python :: 3",
        "Topic :: Multimedia :: Graphics :: 3D Modeling",
    ],
)
