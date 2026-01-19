// Quick debug script to understand the blend shapes generation
const complexState = {
    primary: 'joy',
    intensity: 0.6,
    secondary: ['surprise', 'curiosity'],
    confidence: 0.85,
    timestamp: Date.now(),
    context: { 
        trigger: 'unexpected_positive',
        duration: 2000,
        social_context: 'group_interaction'
    }
};

console.log('Input state:', complexState);
console.log('Primary emotion:', complexState.primary);
console.log('Intensity:', complexState.intensity);
console.log('Secondary emotions:', complexState.secondary);

// Simulate the blend shapes generation logic
const blendShapes = {};
const intensity = complexState.intensity; // 0.6

// Primary emotion: joy with intensity 0.6, weight 1.0
const primaryEffectiveIntensity = intensity * 1.0; // 0.6
console.log('Primary effective intensity:', primaryEffectiveIntensity);

// Secondary emotions: surprise and curiosity with weight 0.6 each
const secondaryWeight = 0.6;
complexState.secondary.forEach((emotion, index) => {
    const weight = secondaryWeight * (1 - index * 0.1); // 0.6, 0.54
    const effectiveIntensity = intensity * weight;
    console.log(`Secondary ${emotion}: weight=${weight}, effectiveIntensity=${effectiveIntensity}`);
});

console.log('Expected blend shapes > 0.1:');
console.log('- Joy (0.6): mouthSmileLeft, mouthSmileRight, cheekSquintLeft, cheekSquintRight');
console.log('- Surprise (0.36): eyeWideLeft, eyeWideRight, browInnerUp, jawOpen, mouthFunnel');
console.log('- Curiosity (0.324): browInnerUp, eyeWideLeft, eyeWideRight, mouthSmileLeft, mouthSmileRight');