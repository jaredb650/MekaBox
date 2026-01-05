console.log('Module paths:', module.paths);
console.log('---');
try {
    const resolved = require.resolve('electron');
    console.log('Resolved electron to:', resolved);
} catch (e) {
    console.log('Could not resolve electron:', e.message);
}
console.log('---');
console.log('Process versions:', process.versions);
