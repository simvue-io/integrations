[Mesh]
  [generated]
    type = GeneratedMeshGenerator
    dim = 3
    nx = 20
    ny = 20
    nz = 20
    xmax = 6
    ymax = 1
    zmax = 1
  []
[]
[Variables]
  [T]
  []
[]
[Kernels]
  [time-derivative]
    type = ADTimeDerivative
    variable = T
  []
  [diffusion-kernel]
    type = ADMatDiffusion    
    variable = T
    diffusivity = diffusivity-property
  []
[]
[Materials]
  [mat-diffusivity]
    type = ADGenericConstantMaterial
    prop_names = 'diffusivity-property'
    prop_values = '0.98'
  []
[]
[VectorPostprocessors]
  [temperature_along_bar]
    type = PointValueSampler
    variable = 'T'
    points = '1 0.5 0.5  3 0.5 0.5  5 0.5 0.5'
    sort_by = 'x'
  []
[]
[Postprocessors]
  [average_temperature]
    type = ElementAverageValue
    variable = 'T'
  []
[]
[BCs]
  [hot]
    type = DirichletBC
    variable = T
    boundary = left
    value = 1000
  []
  [cold]
    type = DirichletBC
    variable = T
    boundary = right
    value = 0
  []
[]
[Problem]
  type = FEProblem
[]
[Executioner]
  type = Transient
  end_time = 100
  dt = 10
  solve_type = NEWTON
[]
[Outputs]
  file_base = ./results/simvue_thermal
  [exodus]
    type = Exodus
  []
  [console]
    type = Console
    output_file = true
  []
  [csv]
    type = CSV
  []
[]