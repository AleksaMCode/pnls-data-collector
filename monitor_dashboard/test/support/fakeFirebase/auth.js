// An in-memory stand-in for the parts of `firebase/auth` the dashboard uses.

const users = new Map();
let observers = [];

function notify() {
  for (const observer of [...observers]) {
    observer(fakeAuthInstance.currentUser);
  }
}

function makeUser(email) {
  const uid = `uid-${email}`;
  return {
    uid,
    email,
    getIdToken: async () => tokenFor(email),
  };
}

const fakeAuthInstance = {
  currentUser: null,
  async signOut() {
    fakeAuthInstance.currentUser = null;
    notify();
  },
};

/** The ID token the fake issues for a user, which the fake stats API accepts. */
export function tokenFor(email) {
  return `test-id-token:${email}`;
}

// --- The SDK surface -------------------------------------------------------------------------------

export function getAuth() {
  return fakeAuthInstance;
}

export function connectAuthEmulator() {}

export function onAuthStateChanged(_auth, observer) {
  observers.push(observer);
  // The real SDK reports the restored session asynchronously.
  queueMicrotask(() => {
    if (observers.includes(observer)) observer(fakeAuthInstance.currentUser);
  });
  return () => {
    observers = observers.filter((o) => o !== observer);
  };
}

export async function signInWithEmailAndPassword(_auth, email, password) {
  if (users.get(email) !== password) {
    const error = new Error('Firebase: Error (auth/invalid-credential).');
    error.code = 'auth/invalid-credential';
    throw error;
  }
  fakeAuthInstance.currentUser = makeUser(email);
  notify();
  return { user: fakeAuthInstance.currentUser };
}

// --- Test controls ---------------------------------------------------------------------------------

export const fakeAuth = {
  reset() {
    users.clear();
    observers = [];
    fakeAuthInstance.currentUser = null;
  },
  addUser(email, password) {
    users.set(email, password);
  },
  /** Starts the test with a restored session, as after a page reload. */
  signInAs(email) {
    fakeAuthInstance.currentUser = makeUser(email);
    notify();
  },
  get currentUser() {
    return fakeAuthInstance.currentUser;
  },
};
