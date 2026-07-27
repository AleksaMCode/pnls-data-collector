import { alpha } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import Box from '@mui/material/Box';
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
  const [sideMenuOpen, setSideMenuOpen] = useState(true);

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
          <SideMenu
            open={sideMenuOpen}
            onToggle={() => setSideMenuOpen((prev) => !prev)}
          />
          {/* Main content */}
          <Box
            component="main"
            sx={(theme) => ({
              flexGrow: 1,
              backgroundColor: theme.vars
                ? `rgba(${theme.vars.palette.background.defaultChannel} / 1)`
                : alpha(theme.palette.background.default, 1),
            })}
          >
            <Box
              sx={(theme) => ({
                position: 'sticky',
                top: 0,
                zIndex: theme.zIndex.drawer - 1,
                isolation: 'isolate',
                flexShrink: 0,
                width: '100%',
                py: 1,
                backgroundColor: theme.vars
                  ? `rgba(${theme.vars.palette.background.defaultChannel} / 0.92)`
                  : alpha(theme.palette.background.default, 0.92),
                backdropFilter: 'blur(6px)',
                borderBottom: `1px solid ${theme.palette.divider}`,
              })}
            >
              <Box sx={{ mx: 3 }}>
                <Header />
              </Box>
            </Box>
            <Box
              sx={{
                mx: 3,
                pb: 5,
                pt: { xs: 0, md: 1.5 },
                mt: { xs: 8, md: 0 },
              }}
            >
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
            </Box>
          </Box>
        </Box>
      </AppTheme>
    </LiveCountProvider>
  );
}
