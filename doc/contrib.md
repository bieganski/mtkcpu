**NOTE:** Most points from that document are natural consequences of points from [Future plans document](future.md), so please read it first.


### About Contributions

We are actively seeking for contributors, and are very happy with everyone interested in `mtkCPU` project. We keenly offer support, code reviews and a place for shaping future of how to achieve Long Term Goals, as defined in [Future plans document](future.md).

### Pull Requests that likely will be accepted

* Bug fixes
* Ports to common devkits/platforms, e.g. Artix or Spartan.
* Anything that improves Debug Module - in terms of functionality, tests coverage, resource usage etc.
* Anything that improves CPU resource usage
* New CPU functionalities, that bring us closer for `mtkCPU` to run more and more software (e.g. Linux kernel), but are not resource-hungry. We target `ice40` platform for now.
* Code quality improvements - e.g. taking advantage of new Amaranth HDL features when possible, Python typing etc.
* CI improvements
* CLI / scripting improvements

### Pull Requests that likely will not be accepted

* New CPU functionalities, whose main benefit is to improve execution time, e.g. `div` op implementation - we don't mind the fact that the CPU is slow.

* Support for (esoteric?) FPGA platforms, if there is no other maintainer able to verify PR due to lack of proper hardware.
