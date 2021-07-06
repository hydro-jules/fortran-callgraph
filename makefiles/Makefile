# directories _________________________________________________________________
BUILD_DIR := ${HOME}/PycharmProjects/fortran-callgraph/fortran-callgraph/makefiles/build
SRC_DIR := ${HOME}/PycharmProjects/jules-vn6.0/jules-vn6.0/jules-vn6.0
INFO_DIR := ${HOME}/PycharmProjects/fortran-callgraph/fortran-callgraph/outputs

# compilers ___________________________________________________________________
FC := /opt/local/bin/gfortran
LD := $(FC)

# names _______________________________________________________________________
LIB := jules_surfacelayer
MOD := surf_couple_extra_surfacelayer

# files to compile  ___________________________________________________________
SRC := $(SRC_DIR)/utilspp/mpi_dummy/mpi_routines.f90
SRC += $(shell cat $(INFO_DIR)/$(MOD)_mod__$(MOD).sources)
DEP := $(INFO_DIR)/$(MOD)_mod__$(MOD).dependencies

OBJS := $(patsubst $(SRC_DIR)/%.f90, $(BUILD_DIR)/%.o, $(SRC))

# rules _______________________________________________________________________
.PHONY: all clean

all: $(LIB)

clean:
# remove the build directory
	rm -f -r $(BUILD_DIR)

# pattern rules _______________________________________________________________
$(LIB): $(OBJS)
	$(LD) -shared -fPIC -I$(BUILD_DIR) -o $@.so $^

$(BUILD_DIR)/%.o: $(SRC_DIR)/%.f90
	$(shell [ ! -d $(@D) ] && mkdir -p $(@D))
	$(FC) -c -J$(BUILD_DIR) -o $@ $<

include $(DEP)
