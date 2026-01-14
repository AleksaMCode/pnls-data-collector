import { initializeApp } from 'firebase/app';
import { getAuth } from 'firebase/auth';

const firebaseConfig = {
  apiKey: 'AIzaSyDrkZiKyIOjJCA5aZSVBJaqtX_LNu7CDNY',
  authDomain: 'pnl-sniffer.firebaseapp.com',
  databaseURL:
    'https://pnl-sniffer-default-rtdb.europe-west1.firebasedatabase.app',
  projectId: 'pnl-sniffer',
  storageBucket: 'pnl-sniffer.firebasestorage.app',
  messagingSenderId: '480790480165',
  appId: '1:480790480165:web:f8ed113c483903452086cc',
};

const app = initializeApp(firebaseConfig);
const auth = getAuth(app);

export { app, auth };
