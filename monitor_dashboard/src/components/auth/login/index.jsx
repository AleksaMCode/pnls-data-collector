import { useState } from 'react';
import { Navigate } from 'react-router-dom';
import { firebaseSignInWithEmailAndPassword } from '../../../firebase/auth';
import { useAuth } from '../../../context/authContext';

import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import CssBaseline from '@mui/material/CssBaseline';
import FormLabel from '@mui/material/FormLabel';
import FormControl from '@mui/material/FormControl';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import Stack from '@mui/material/Stack';
import Card from '@mui/material/Card';
import Avatar from '@mui/material/Avatar';
import Alert from '@mui/material/Alert';
import LockOutlinedIcon from '@mui/icons-material/LockOutlined';
import { Visibility, VisibilityOff } from '@mui/icons-material';
import { IconButton, InputAdornment } from '@mui/material';

// Created using template: https://github.com/mui/material-ui/tree/v7.3.7/docs/data/material/getting-started/templates/sign-in

export default function Login() {
  const { userLoggedIn } = useAuth();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isSigningIn, setIsSigningIn] = useState(false);
  const [emailError, setEmailError] = useState(false);
  const [emailErrorMessage, setEmailErrorMessage] = useState('');
  const [passwordError, setPasswordError] = useState(false);
  const [passwordErrorMessage, setPasswordErrorMessage] = useState('');
  const [errorMessage, setErrorMessage] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  const handleClickShowPassword = () => setShowPassword(!showPassword);
  const handleMouseDownPassword = (event) => event.preventDefault();

  const validateInputs = () => {
    let isValid = true;

    if (!email || !/\S+@\S+\.\S+/.test(email)) {
      setEmailError(true);
      setEmailErrorMessage('Please enter a valid email address.');
      isValid = false;
    } else {
      setEmailError(false);
      setEmailErrorMessage('');
    }

    if (!password || password.length < 6) {
      setPasswordError(true);
      setPasswordErrorMessage('Password must be at least 6 characters long.');
      isValid = false;
    } else {
      setPasswordError(false);
      setPasswordErrorMessage('');
    }

    return isValid;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!validateInputs()) return;

    if (!isSigningIn) {
      setIsSigningIn(true);
      setErrorMessage('');
      try {
        await firebaseSignInWithEmailAndPassword(email, password);
      } catch (err) {
        setErrorMessage('Failed to sign in. Please try again.');
        setIsSigningIn(false);
      }
    }
  };

  return (
    <>
      <CssBaseline />

      {userLoggedIn && <Navigate to="/home" replace />}

      <Stack
        sx={{
          position: 'fixed',
          inset: 0,
          minHeight: '100vh',
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          p: 2,
          background:
            'radial-gradient(ellipse at center, #f0f7ff 0%, #ffffff 100%)',
        }}
      >
        <Card
          variant="outlined"
          sx={{
            width: '100%',
            maxWidth: 450,
            p: 4,
            display: 'flex',
            flexDirection: 'column',
            gap: 2,
            boxShadow:
              '0px 5px 15px rgba(0,0,0,0.05), 0px 15px 35px rgba(0,0,0,0.05)',
          }}
        >
          <Box sx={{ display: 'flex', justifyContent: 'center', mb: 2 }}>
            <Avatar sx={{ bgcolor: '#1976d2', width: 56, height: 56 }}>
              <LockOutlinedIcon />
            </Avatar>
          </Box>

          <Typography
            component="h1"
            sx={{
              fontSize: '2rem',
              textAlign: 'center',
              fontWeight: 600,
            }}
          >
            Sign in
          </Typography>

          <Typography
            variant="body2"
            sx={{ textAlign: 'center', color: '#666', mb: 2 }}
          >
            Sign in to continue to the PNLS-DC Monitoring Dashboard
          </Typography>

          <Box
            component="form"
            onSubmit={handleSubmit}
            noValidate
            sx={{
              display: 'flex',
              flexDirection: 'column',
              gap: 2,
            }}
          >
            {errorMessage && <Alert severity="error">{errorMessage}</Alert>}

            <FormControl>
              <FormLabel>Email</FormLabel>
              <TextField
                error={emailError}
                helperText={emailErrorMessage}
                type="email"
                placeholder="name@email.com"
                required
                fullWidth
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </FormControl>

            <FormControl>
              <FormLabel>Password</FormLabel>
              <TextField
                error={passwordError}
                helperText={passwordErrorMessage}
                type={showPassword ? 'text' : 'password'}
                placeholder="••••••••"
                required
                fullWidth
                value={password}
                color={passwordError ? 'error' : 'primary'}
                onChange={(e) => setPassword(e.target.value)}
                slotProps={{
                  input: {
                    endAdornment: (
                      <InputAdornment position="end">
                        <IconButton
                          onClick={handleClickShowPassword}
                          edge="end"
                        >
                          {showPassword ? <VisibilityOff /> : <Visibility />}
                        </IconButton>
                      </InputAdornment>
                    ),
                  },
                }}
              />
            </FormControl>

            <Button
              type="submit"
              variant="contained"
              disabled={isSigningIn}
              sx={{ mt: 1 }}
            >
              {isSigningIn ? 'Signing in...' : 'Sign in'}
            </Button>
          </Box>
        </Card>
      </Stack>
    </>
  );
}
