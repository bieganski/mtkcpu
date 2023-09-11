
### Long-term goal

The future of the project is DM (Debug Module) oriented, not CPU oriented.
We are trying to create a "Debug Plugin" that can be easily ported to any CPU basic-ISA implementation.

CPU implementation is for us only a tool to verify if the DM works fine - we don't mind switching to different core implementation at some maturity point.

In future one may expect DM to be placed in a seaprate repository, and the `mtkcpu` will keep it as a submodule.


### Challenges

Debug Module is very tightly coupled with the CPU core. It needs following powers:

* Stop/resume the CPU at any time
* read/write CPU registers (CSRs as well)
* read/write system memory

and more, depdending on how much debugging capabilities do we need.

It is a big challenge to design an interface with such a small surface, that is easy to use by third-party core implementations. It also requires decent and explanatory unit tests set, so that the integrator is given immediate feedback on potential integration issues.


### Current idea

Currently we consider a similar approach as [`riscv-formal`](https://github.com/SymbioticEDA/riscv-formal/) authors did.

What `riscv-formal` does, is to define a set of signals with specific semantics, that give some insights on what is the CPU currently doing. Unfortunately we cannot reuse it, because all the `riscv-formal` interface signals are of `output` type (refer to [this document](https://github.com/SymbioticEDA/riscv-formal/blob/master/docs/rvfi.md)), as we need DM to be able to issue requests as well, e.g. `haltrequest`. 

CPU implementation integrator willing to use our Debug Mode would have drive all the signals that the DM needs, and add a logic that we require that is a response to signals controlled by DM. The point is for that set of signals to be as small as possible, for a smooth integration.

