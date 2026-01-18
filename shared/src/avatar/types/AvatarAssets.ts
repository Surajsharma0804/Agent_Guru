/**
 * Avatar asset management and loading types
 */

import { Platform, QualityLevel, DigitalSignature, BoundingBox } from './Common';

/**
 * Complete avatar asset collection
 */
export interface AvatarAssets {
  version: string;
  platform: Platform;
  quality: QualityLevel;
  
  // Core 3D Assets
  meshes: MeshAssetCollection;
  textures: TextureAssetCollection;
  animations: AnimationAssetCollection;
  shaders: ShaderAssetCollection;
  
  // Audio Assets
  audio?: AudioAssetCollection;
  
  // Metadata and Security
  metadata: AssetMetadata;
  signature: DigitalSignature;
  
  // Loading and Caching
  loadingStrategy: LoadingStrategy;
  cachePolicy: CachePolicy;
}

/**
 * Mesh asset collection organized by type
 */
export interface MeshAssetCollection {
  // Core meshes
  head: MeshAsset;
  body?: MeshAsset; // Optional for face-only platforms
  hair: MeshAsset;
  
  // Accessories
  accessories?: MeshAsset[];
  clothing?: MeshAsset[];
  
  // Animation rigs
  facialRig: FacialRig;
  bodyRig?: BodyRig;
  
  // Morph targets
  morphTargets: MorphTargetSet;
  blendShapes: BlendShapeSet;
}

/**
 * Individual mesh asset
 */
export interface MeshAsset {
  id: string;
  name: string;
  format: MeshFormat;
  lodLevels: LODLevel[];
  vertexCount: number;
  triangleCount: number;
  boundingBox: BoundingBox;
  
  // Asset location and integrity
  url: string;
  localPath?: string;
  checksum: string;
  size: number; // bytes
  
  // Rendering properties
  materials: MaterialReference[];
  uvChannels: number;
  vertexColors: boolean;
  skinned: boolean;
  
  // Optimization data
  compressionLevel: number;
  optimizationFlags: MeshOptimizationFlag[];
}

/**
 * Supported mesh formats
 */
export type MeshFormat = 'gltf' | 'glb' | 'usdz' | 'fbx' | 'obj' | 'ply';

/**
 * Level of detail configuration
 */
export interface LODLevel {
  level: number; // 0 = highest quality
  distance: number; // rendering distance threshold
  vertexReduction: number; // percentage reduction 0.0 to 1.0
  textureReduction: number; // percentage reduction 0.0 to 1.0
  featureDisabling: string[]; // features to disable at this LOD
  targetTriangleCount: number;
  qualityScore: number; // 0.0 to 1.0
}

/**
 * Material reference for mesh assets
 */
export interface MaterialReference {
  id: string;
  name: string;
  textureSlots: TextureSlot[];
  shaderReference: string;
  properties: MaterialProperties;
}

/**
 * Texture slot assignment
 */
export interface TextureSlot {
  type: TextureType;
  textureId: string;
  uvChannel: number;
  tiling: import('./Common').Vector2;
  offset: import('./Common').Vector2;
}

/**
 * Texture types for different material properties
 */
export type TextureType = 
  | 'diffuse'
  | 'normal'
  | 'specular'
  | 'roughness'
  | 'metallic'
  | 'emission'
  | 'occlusion'
  | 'height'
  | 'subsurface';

/**
 * Material properties
 */
export interface MaterialProperties {
  baseColor: import('./Common').ColorValue;
  metallic: number; // 0.0 to 1.0
  roughness: number; // 0.0 to 1.0
  emission: import('./Common').ColorValue;
  transparency: number; // 0.0 to 1.0
  subsurface: number; // 0.0 to 1.0
  ior: number; // index of refraction
}

/**
 * Mesh optimization flags
 */
export type MeshOptimizationFlag = 
  | 'vertex_cache_optimization'
  | 'overdraw_optimization'
  | 'vertex_fetch_optimization'
  | 'triangle_strip_conversion'
  | 'vertex_deduplication'
  | 'normal_compression'
  | 'uv_compression'
  | 'quantization';

/**
 * Facial animation rig
 */
export interface FacialRig {
  id: string;
  version: string;
  
  // Bone structure
  bones: RigBone[];
  
  // Blend shapes and morph targets
  blendShapes: BlendShapeDefinition[];
  morphTargets: MorphTargetDefinition[];
  
  // Control systems
  controllers: FacialController[];
  
  // Constraints and limits
  constraints: RigConstraint[];
}

/**
 * Body animation rig (for full-body platforms)
 */
export interface BodyRig {
  id: string;
  version: string;
  
  // Skeletal structure
  skeleton: SkeletonDefinition;
  
  // IK chains
  ikChains: IKChain[];
  
  // Control systems
  controllers: BodyController[];
  
  // Physics simulation
  physicsProperties?: PhysicsProperties;
}

/**
 * Rig bone definition
 */
export interface RigBone {
  id: string;
  name: string;
  parent?: string;
  position: import('./Common').Vector3;
  rotation: import('./Common').Vector3;
  scale: import('./Common').Vector3;
  length: number;
  influence: number; // 0.0 to 1.0
}

/**
 * Blend shape definition
 */
export interface BlendShapeDefinition {
  id: string;
  name: string;
  category: 'expression' | 'viseme' | 'corrective' | 'custom';
  vertexDeltas: Float32Array;
  normalDeltas?: Float32Array;
  weight: number; // default weight 0.0 to 1.0
  clampRange: [number, number]; // min/max weight values
}

/**
 * Morph target definition
 */
export interface MorphTargetDefinition {
  id: string;
  name: string;
  type: 'shape' | 'pose' | 'corrective';
  targetMesh: string; // reference to mesh asset
  deltaVertices: Float32Array;
  deltaNormals?: Float32Array;
  weight: number; // 0.0 to 1.0
}

/**
 * Facial animation controller
 */
export interface FacialController {
  id: string;
  type: 'blend_shape' | 'bone' | 'constraint';
  targets: string[]; // target blend shapes or bones
  parameters: ControllerParameter[];
  curves: import('./Common').AnimationCurve[];
}

/**
 * Body animation controller
 */
export interface BodyController {
  id: string;
  type: 'fk' | 'ik' | 'constraint' | 'physics';
  bones: string[];
  parameters: ControllerParameter[];
  limits: ControllerLimits;
}

/**
 * Controller parameter
 */
export interface ControllerParameter {
  name: string;
  type: 'float' | 'vector2' | 'vector3' | 'quaternion';
  defaultValue: number | number[];
  range: [number, number];
  curve?: import('./Common').AnimationCurve;
}

/**
 * Controller limits and constraints
 */
export interface ControllerLimits {
  rotationLimits?: {
    x: [number, number];
    y: [number, number];
    z: [number, number];
  };
  positionLimits?: {
    x: [number, number];
    y: [number, number];
    z: [number, number];
  };
  scaleLimits?: {
    x: [number, number];
    y: [number, number];
    z: [number, number];
  };
}

/**
 * Rig constraint definition
 */
export interface RigConstraint {
  id: string;
  type: 'look_at' | 'aim' | 'parent' | 'position' | 'rotation' | 'scale';
  source: string; // source bone/object
  target: string; // target bone/object
  influence: number; // 0.0 to 1.0
  parameters: Record<string, unknown>;
}

/**
 * Skeletal definition for body rig
 */
export interface SkeletonDefinition {
  bones: RigBone[];
  hierarchy: BoneHierarchy;
  bindPose: BindPose;
  retargeting?: RetargetingMap;
}

/**
 * Bone hierarchy structure
 */
export interface BoneHierarchy {
  root: string; // root bone ID
  children: Record<string, string[]>; // parent -> children mapping
  depth: Record<string, number>; // bone -> depth mapping
}

/**
 * Bind pose for skeletal animation
 */
export interface BindPose {
  boneTransforms: Record<string, Transform>;
  inverseBindMatrices: Record<string, number[]>; // 4x4 matrices
}

/**
 * Transform definition
 */
export interface Transform {
  position: import('./Common').Vector3;
  rotation: import('./Common').Vector3; // euler angles or quaternion
  scale: import('./Common').Vector3;
}

/**
 * Retargeting map for animation compatibility
 */
export interface RetargetingMap {
  boneMapping: Record<string, string>; // source -> target bone mapping
  scaleFactors: Record<string, number>;
  rotationOffsets: Record<string, import('./Common').Vector3>;
}

/**
 * IK chain definition
 */
export interface IKChain {
  id: string;
  name: string;
  bones: string[]; // ordered from root to end effector
  target: string; // target object/bone
  solver: 'ccd' | 'fabrik' | 'analytical';
  iterations: number;
  tolerance: number;
  constraints: IKConstraint[];
}

/**
 * IK constraint
 */
export interface IKConstraint {
  type: 'hinge' | 'ball_socket' | 'twist' | 'planar';
  bone: string;
  limits: ControllerLimits;
  stiffness: number; // 0.0 to 1.0
}

/**
 * Physics properties for dynamic simulation
 */
export interface PhysicsProperties {
  enabled: boolean;
  gravity: import('./Common').Vector3;
  damping: number; // 0.0 to 1.0
  stiffness: number; // 0.0 to 1.0
  collisionShapes: CollisionShape[];
  constraints: PhysicsConstraint[];
}

/**
 * Collision shape for physics
 */
export interface CollisionShape {
  type: 'sphere' | 'box' | 'capsule' | 'mesh';
  bone: string;
  parameters: Record<string, number>;
  material: PhysicsMaterial;
}

/**
 * Physics material properties
 */
export interface PhysicsMaterial {
  friction: number; // 0.0 to 1.0
  restitution: number; // 0.0 to 1.0
  density: number;
}

/**
 * Physics constraint
 */
export interface PhysicsConstraint {
  type: 'distance' | 'hinge' | 'ball_socket' | 'spring';
  bodyA: string;
  bodyB: string;
  parameters: Record<string, number>;
}

/**
 * Morph target set
 */
export interface MorphTargetSet {
  version: string;
  targets: MorphTargetDefinition[];
  categories: MorphTargetCategory[];
  presets: MorphTargetPreset[];
}

/**
 * Morph target category
 */
export interface MorphTargetCategory {
  name: string;
  targets: string[]; // target IDs
  exclusive: boolean; // whether targets are mutually exclusive
  maxWeight: number; // maximum combined weight
}

/**
 * Morph target preset
 */
export interface MorphTargetPreset {
  name: string;
  description: string;
  weights: Record<string, number>; // target ID -> weight
  tags: string[];
}

/**
 * Blend shape set
 */
export interface BlendShapeSet {
  version: string;
  shapes: BlendShapeDefinition[];
  groups: BlendShapeGroup[];
  correctives: CorrectiveBlendShape[];
}

/**
 * Blend shape group
 */
export interface BlendShapeGroup {
  name: string;
  shapes: string[]; // shape IDs
  type: 'additive' | 'exclusive' | 'normalized';
  maxWeight: number;
}

/**
 * Corrective blend shape
 */
export interface CorrectiveBlendShape {
  id: string;
  name: string;
  triggers: BlendShapeTrigger[];
  shape: BlendShapeDefinition;
  strength: number; // 0.0 to 1.0
}

/**
 * Blend shape trigger condition
 */
export interface BlendShapeTrigger {
  shapeId: string;
  minWeight: number;
  maxWeight: number;
  curve?: import('./Common').AnimationCurve;
}

/**
 * Texture asset collection
 */
export interface TextureAssetCollection {
  diffuse: TextureAsset[];
  normal: TextureAsset[];
  specular: TextureAsset[];
  roughness: TextureAsset[];
  metallic: TextureAsset[];
  emission?: TextureAsset[];
  occlusion?: TextureAsset[];
  height?: TextureAsset[];
  subsurface?: TextureAsset[];
}

/**
 * Individual texture asset
 */
export interface TextureAsset {
  id: string;
  name: string;
  type: TextureType;
  format: TextureFormat;
  resolution: TextureResolution;
  mipmaps: boolean;
  compression: TextureCompression;
  
  // Asset location and integrity
  url: string;
  localPath?: string;
  checksum: string;
  size: number; // bytes
  
  // Texture properties
  wrapMode: TextureWrapMode;
  filterMode: TextureFilterMode;
  anisotropy: number;
  
  // Platform variants
  platformVariants?: Record<Platform, string>; // platform -> URL mapping
}

/**
 * Supported texture formats
 */
export type TextureFormat = 'png' | 'jpg' | 'webp' | 'ktx2' | 'dds' | 'astc' | 'etc2' | 'bc7';

/**
 * Texture resolution specification
 */
export interface TextureResolution {
  width: number;
  height: number;
  aspectRatio: number;
}

/**
 * Texture compression settings
 */
export interface TextureCompression {
  algorithm: string;
  quality: number; // 0.0 to 1.0
  lossless: boolean;
  compressionRatio: number;
}

/**
 * Texture wrap modes
 */
export type TextureWrapMode = 'repeat' | 'clamp' | 'mirror' | 'border';

/**
 * Texture filter modes
 */
export type TextureFilterMode = 'nearest' | 'linear' | 'bilinear' | 'trilinear' | 'anisotropic';

/**
 * Animation asset collection
 */
export interface AnimationAssetCollection {
  idle: AnimationAsset[];
  expressions: AnimationAsset[];
  gestures: AnimationAsset[];
  transitions: AnimationAsset[];
  breathing: AnimationAsset;
  blinking: AnimationAsset;
  lipSync: LipSyncAnimationSet;
}

/**
 * Individual animation asset
 */
export interface AnimationAsset {
  id: string;
  name: string;
  duration: number; // seconds
  fps: number;
  looping: boolean;
  blendable: boolean;
  priority: number;
  tags: string[];
  
  // Animation data
  keyframes: AnimationKeyframe[];
  curves: AnimationCurveSet;
  
  // Metadata
  category: AnimationCategory;
  emotionalContext?: string[];
  gestureType?: string;
  
  // Asset location
  url: string;
  checksum: string;
  size: number; // bytes
}

/**
 * Animation categories
 */
export type AnimationCategory = 
  | 'idle'
  | 'expression'
  | 'gesture'
  | 'transition'
  | 'breathing'
  | 'blinking'
  | 'lip_sync'
  | 'custom';

/**
 * Animation keyframe
 */
export interface AnimationKeyframe {
  time: number; // seconds
  transforms: Record<string, Transform>;
  morphWeights?: Record<string, number>;
  blendShapeWeights?: Record<string, number>;
  customProperties?: Record<string, unknown>;
}

/**
 * Animation curve set
 */
export interface AnimationCurveSet {
  position: Record<string, import('./Common').AnimationCurve>;
  rotation: Record<string, import('./Common').AnimationCurve>;
  scale: Record<string, import('./Common').AnimationCurve>;
  morphTargets: Record<string, import('./Common').AnimationCurve>;
  blendShapes: Record<string, import('./Common').AnimationCurve>;
}

/**
 * Lip sync animation set
 */
export interface LipSyncAnimationSet {
  visemes: Record<string, AnimationAsset>; // viseme -> animation
  transitions: Record<string, AnimationAsset>; // viseme pair -> transition
  emotionalVariants: Record<string, Record<string, AnimationAsset>>; // emotion -> viseme -> animation
}

/**
 * Shader asset collection
 */
export interface ShaderAssetCollection {
  vertex: ShaderAsset[];
  fragment: ShaderAsset[];
  compute?: ShaderAsset[];
  programs: ShaderProgram[];
}

/**
 * Individual shader asset
 */
export interface ShaderAsset {
  id: string;
  name: string;
  type: ShaderType;
  version: string; // shader language version
  source: string;
  
  // Shader interface
  uniforms: ShaderUniform[];
  attributes: ShaderAttribute[];
  varyings: ShaderVarying[];
  
  // Platform compatibility
  platforms: Platform[];
  fallbacks: string[]; // fallback shader IDs
  
  // Asset location
  url: string;
  checksum: string;
  size: number; // bytes
}

/**
 * Shader types
 */
export type ShaderType = 'vertex' | 'fragment' | 'geometry' | 'compute' | 'tessellation';

/**
 * Shader uniform definition
 */
export interface ShaderUniform {
  name: string;
  type: ShaderDataType;
  defaultValue?: unknown;
  description?: string;
  range?: [number, number];
}

/**
 * Shader attribute definition
 */
export interface ShaderAttribute {
  name: string;
  type: ShaderDataType;
  location: number;
  normalized: boolean;
}

/**
 * Shader varying definition
 */
export interface ShaderVarying {
  name: string;
  type: ShaderDataType;
  interpolation: 'smooth' | 'flat' | 'noperspective';
}

/**
 * Shader data types
 */
export type ShaderDataType = 
  | 'float'
  | 'vec2'
  | 'vec3'
  | 'vec4'
  | 'int'
  | 'ivec2'
  | 'ivec3'
  | 'ivec4'
  | 'bool'
  | 'bvec2'
  | 'bvec3'
  | 'bvec4'
  | 'mat2'
  | 'mat3'
  | 'mat4'
  | 'sampler2D'
  | 'samplerCube';

/**
 * Shader program linking vertex and fragment shaders
 */
export interface ShaderProgram {
  id: string;
  name: string;
  vertexShader: string; // shader asset ID
  fragmentShader: string; // shader asset ID
  geometryShader?: string; // shader asset ID
  
  // Program properties
  uniforms: Record<string, ShaderUniform>;
  attributes: Record<string, ShaderAttribute>;
  
  // Rendering state
  blendMode: BlendMode;
  depthTest: boolean;
  depthWrite: boolean;
  cullMode: CullMode;
}

/**
 * Blend modes for rendering
 */
export type BlendMode = 'opaque' | 'alpha' | 'additive' | 'multiply' | 'screen';

/**
 * Face culling modes
 */
export type CullMode = 'none' | 'front' | 'back';

/**
 * Audio asset collection (optional)
 */
export interface AudioAssetCollection {
  breathing: AudioAsset[];
  heartbeat?: AudioAsset[];
  ambientSounds?: AudioAsset[];
  voiceSamples?: AudioAsset[];
}

/**
 * Individual audio asset
 */
export interface AudioAsset {
  id: string;
  name: string;
  format: AudioFormat;
  duration: number; // seconds
  sampleRate: number; // Hz
  channels: number;
  bitDepth: number;
  
  // Asset location
  url: string;
  checksum: string;
  size: number; // bytes
  
  // Audio properties
  looping: boolean;
  volume: number; // 0.0 to 1.0
  pitch: number; // 0.5 to 2.0
  spatialAudio: boolean;
}

/**
 * Supported audio formats
 */
export type AudioFormat = 'wav' | 'mp3' | 'ogg' | 'aac' | 'flac';

/**
 * Asset metadata for integrity and versioning
 */
export interface AssetMetadata {
  version: string;
  created: Date;
  lastModified: Date;
  
  // Size and count information
  totalSize: number; // bytes
  assetCount: number;
  
  // Integrity and security
  signature: DigitalSignature;
  checksumAlgorithm: string;
  
  // Dependencies and compatibility
  dependencies: AssetDependency[];
  compatibility: CompatibilityInfo[];
  
  // Build information
  buildInfo: BuildInfo;
}

/**
 * Asset dependency information
 */
export interface AssetDependency {
  id: string;
  version: string;
  type: 'required' | 'optional' | 'fallback';
  platform?: Platform;
}

/**
 * Compatibility information
 */
export interface CompatibilityInfo {
  platform: Platform;
  minVersion: string;
  maxVersion?: string;
  features: string[];
  limitations: string[];
}

/**
 * Build information
 */
export interface BuildInfo {
  buildNumber: string;
  buildDate: Date;
  buildTool: string;
  buildConfiguration: string;
  optimizationLevel: string;
  targetPlatforms: Platform[];
}

/**
 * Asset loading strategy
 */
export interface LoadingStrategy {
  priority: LoadingPriority;
  preloading: PreloadingStrategy;
  streaming: StreamingStrategy;
  caching: CachingStrategy;
}

/**
 * Loading priority levels
 */
export type LoadingPriority = 'critical' | 'high' | 'normal' | 'low' | 'background';

/**
 * Preloading strategy
 */
export interface PreloadingStrategy {
  enabled: boolean;
  assets: string[]; // asset IDs to preload
  conditions: PreloadingCondition[];
  maxConcurrent: number;
}

/**
 * Preloading conditions
 */
export interface PreloadingCondition {
  type: 'platform' | 'network' | 'memory' | 'battery' | 'user_preference';
  condition: string;
  value: unknown;
}

/**
 * Streaming strategy for large assets
 */
export interface StreamingStrategy {
  enabled: boolean;
  chunkSize: number; // bytes
  bufferSize: number; // bytes
  compressionEnabled: boolean;
  adaptiveQuality: boolean;
}

/**
 * Caching strategy
 */
export interface CachingStrategy {
  enabled: boolean;
  maxSize: number; // bytes
  ttl: number; // time to live in milliseconds
  evictionPolicy: 'lru' | 'lfu' | 'fifo' | 'random';
  persistentCache: boolean;
}

/**
 * Cache policy for asset management
 */
export interface CachePolicy {
  maxMemoryUsage: number; // bytes
  maxDiskUsage: number; // bytes
  retentionTime: number; // milliseconds
  compressionEnabled: boolean;
  encryptionEnabled: boolean;
  cleanupInterval: number; // milliseconds
}