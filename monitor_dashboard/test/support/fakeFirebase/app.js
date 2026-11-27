// A stand-in for `firebase/app`: the fakes in this folder need no real app.
export function initializeApp(options) {
  return { name: '[DEFAULT]', options };
}
