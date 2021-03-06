"""
Generated by CHARMM-GUI (http://www.charmm-gui.org)

openmm_run.py

This program is OpenMM running scripts written in python.

Correspondance: jul316@lehigh.edu or wonpil@lehigh.edu
Last update: November 11, 2014
"""

from __future__ import print_function
import sys
import os

from omm_readinputs import *
from omm_readparams import *
from omm_vfswitch import *
from omm_barostat import *
from omm_restraints import *

from simtk.unit import *
from simtk.openmm import *
from simtk.openmm.app import *

if len(sys.argv) != 2:
    print("useage: python openmm_run.py inputFile")
    exit()

# Load parameters
print("Loading parameters")
inputs = read_inputs(sys.argv[1])
params = read_params(inputs.toppar_path)
psf = read_psf(inputs.input_psf)
crd = read_crd(inputs.input_crd)
if inputs.input_box:
    psf = read_box(psf, inputs.input_box)
else:
    psf = gen_box(psf, crd)

# Build system
system = psf.createSystem(params, nonbondedMethod=inputs.coulomb,
                          nonbondedCutoff=inputs.r_off*nanometers,
                          constraints=inputs.cons,
                          ewaldErrorTolerance=inputs.ewald_Tol)
if inputs.vdw == 'Force-switch': system = vfswitch(system, psf, inputs.r_on, inputs.r_off)
if inputs.pcouple == 'yes':      system = barostat(system, inputs.temp, inputs.p_ref, inputs.p_type, inputs.p_scale, inputs.p_XYMode, inputs.p_ZMode, inputs.p_tens, inputs.p_freq)
if inputs.rest == 'yes':         system = restraints(system, crd, inputs.fc_bb, inputs.fc_sc, inputs.fc_lpos, inputs.fc_ldih, inputs.fc_cdih)
integrator = LangevinIntegrator(inputs.temp*kelvin, inputs.fric_coeff/picosecond, inputs.dt*picoseconds)

# Set platform
platform = Platform.getPlatformByName('CUDA')
prop = dict(CudaPrecision='single')

# Build simulation context
simulation = Simulation(psf.topology, system, integrator, platform, prop)
simulation.context.setPositions(crd.positions)
if inputs.input_rst:
    with open(inputs.input_rst, 'r') as f:
        simulation.context.setState(XmlSerializer.deserialize(f.read()))
if inputs.input_chk:
    with open(inputs.input_chk, 'rb') as f:
        simulation.context.loadCheckpoint(f.read())

# Calculate initial system energy
print("\nInitial system energy")
print(simulation.context.getState(getEnergy=True).getPotentialEnergy())

# Energy minimization
if inputs.mini_nstep > 0:
    print("\nEnergy minimization: %s steps" % inputs.mini_nstep)
    simulation.minimizeEnergy(tolerance=inputs.mini_Tol*kilojoule/mole, maxIterations=inputs.mini_nstep)
    print(simulation.context.getState(getEnergy=True).getPotentialEnergy())

# Generate initial velocities
if inputs.gen_vel == 'yes':
    print("\nGenerate initial velocities")
    if inputs.gen_seed:
        simulation.context.setVelocitiesToTemperature(inputs.gen_temp, inputs.gen_seed)
    else:
        simulation.context.setVelocitiesToTemperature(inputs.gen_temp)

# Production
if inputs.nstep > 0:
    print("\nMD run: %s steps" % inputs.nstep)
    if inputs.nstdcd > 0: simulation.reporters.append(DCDReporter(inputs.output_dcd, inputs.nstdcd))
    simulation.reporters.append(
        StateDataReporter(sys.stdout, inputs.nstout, step=True, time=True, potentialEnergy=True, temperature=True, progress=True,
                          remainingTime=True, speed=True, totalSteps=inputs.nstep, separator='\t')
    )
    simulation.step(inputs.nstep)

# Write restart file
if inputs.output_rst:
    state = simulation.context.getState( getPositions=True, getVelocities=True )
    with open(inputs.output_rst, 'w') as f:
        f.write(XmlSerializer.serialize(state))

if inputs.output_chk:
    with open(inputs.output_chk, 'wb') as f:
        f.write(simulation.context.createCheckpoint())

