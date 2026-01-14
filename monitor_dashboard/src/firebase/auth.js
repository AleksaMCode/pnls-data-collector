import { auth } from './firebase';
import { signInWithEmailAndPassword } from 'firebase/auth';

export const firebaseSignInWithEmailAndPassword = (email, password) => {
  return signInWithEmailAndPassword(auth, email, password);
};

export const firebaseSignOut = () => {
  return auth.signOut();
};
