ifeq ($(PROJ_NAME),)
$(error PROJ_NAME variable not set! Makefile.mk is only includable!)
endif

# TODO at some point we will need it.
# vpath %.S ../bsp/
# vpath %.cc ../bsp/


TOOLCHAIN := riscv-none-elf-
CC := $(TOOLCHAIN)g++
LD := $(TOOLCHAIN)ld

MARCH := rv32i_zicsr
ARCH_FLAGS := -march=$(MARCH) -mabi=ilp32 -DUSE_GP

MAKEFILE_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
GIT_ROOT := $(MAKEFILE_DIR)/../../

LINKER_SCRIPT ?= $(GIT_ROOT)/sw/common/linker.ld

LDFLAGS += -T$(LINKER_SCRIPT) --gc-sections

CCFLAGS += -ffunction-sections -fdata-sections  # for linker garbage collection
CCFLAGS += $(ARCH_FLAGS)
CCFLAGS += -std=c++17 # standard library
CCFLAGS += -Os # reduce code size at most
CCFLAGS += -nostartfiles # we provide custom start.S file
CCFLAGS += -fno-exceptions # don't create .eh-frame sections etc; reduces code size
CCFLAGS += -I../bsp/
CCFLAGS += -Isrc/ # working directory

SRCS := $(wildcard src/*.cc) \
	$(wildcard src/*.S) \
        ../bsp/start.S \
		../bsp/utils.cc

$(info == Compilation: Found following source files: $(SRCS))

OBJDIR := build

OBJS := $(SRCS)
OBJS := $(abspath $(OBJS))
OBJS := $(subst $(COLON),,$(OBJS))
OBJS := $(OBJS:.cc=.o)
OBJS := $(OBJS:.S=.o)
OBJS := $(addprefix $(OBJDIR)/,$(OBJS))

$(info == Compilation: Corresponding object files: $(OBJS))

CFLAGS := error_use_cc_only
CXXFLAGS := error_use_cc_only

all: $(OBJDIR)/$(PROJ_NAME).elf

$(OBJDIR)/%.elf: $(OBJS) | $(OBJDIR)
	$(LD) $(LDFLAGS) -o $@ $^ $(LIBS)

$(OBJDIR)/%.o: %.cc
	@mkdir -p $(dir $@)
	$(CC) $(CCFLAGS) -c $< -o $@

$(OBJDIR)/%.o: %.S
	@mkdir -p $(dir $@)
	$(CC) $(CCFLAGS) -c $< -o $@

# grab some tabs here -> -> 			

$(OBJDIR):
	@mkdir -p $@
