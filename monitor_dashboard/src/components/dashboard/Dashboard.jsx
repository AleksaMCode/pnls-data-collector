import { alpha } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import Box from '@mui/material/Box';
import Stack from '@mui/material/Stack';
import Header from './Header';
import {
  chartsCustomizations,
  dataGridCustomizations,
  datePickersCustomizations,
  treeViewCustomizations,
} from '../../theme/customizations';
import AppTheme from '../../theme/AppTheme';
import SideMenu from './SideMenu';
import { LiveCountProvider } from './LiveCountProvider';
import { Outlet, useLocation } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { CircularProgress, Fade } from '@mui/material';

const xThemeComponents = {
  ...chartsCustomizations,
  ...dataGridCustomizations,
  ...datePickersCustomizations,
  ...treeViewCustomizations,
};

export default function Dashboard(props) {
  const location = useLocation();
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    const t = setTimeout(() => setLoading(false), 200);
    return () => clearTimeout(t);
  }, [location.pathname]);
  return (
    <LiveCountProvider>
      <AppTheme {...props} themeComponents={xThemeComponents}>
        <CssBaseline enableColorScheme />
        <Box sx={{ display: 'flex' }}>
          <SideMenu />
          {/* Main content */}
          <Box
            component="main"
            sx={(theme) => ({
              flexGrow: 1,
              backgroundColor: theme.vars
                ? `rgba(${theme.vars.palette.background.defaultChannel} / 1)`
                : alpha(theme.palette.background.default, 1),
              overflow: 'auto',
            })}
          >
            <Stack
              spacing={2}
              sx={{
                alignItems: 'center',
                mx: 3,
                pb: 5,
                mt: { xs: 8, md: 0 },
              }}
            >
              <Header />
              {loading ? (
                <Fade in>
                  <Box
                    sx={{
                      flexGrow: 1,
                      minHeight: '60vh', // ensures vertical centering
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    <CircularProgress size={32} />
                  </Box>
                </Fade>
              ) : (
                <Fade in>
                  <Box sx={{ width: '100%' }}>
                    <Outlet />
                  </Box>
                </Fade>
              )}
            </Stack>
          </Box>
        </Box>
      </AppTheme>
    </LiveCountProvider>
  );
}
