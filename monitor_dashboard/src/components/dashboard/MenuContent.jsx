import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemButton from '@mui/material/ListItemButton';
import ListItemIcon from '@mui/material/ListItemIcon';
import ListItemText from '@mui/material/ListItemText';
import Stack from '@mui/material/Stack';
import HomeRoundedIcon from '@mui/icons-material/HomeRounded';
import SettingsRoundedIcon from '@mui/icons-material/SettingsRounded';
import InfoRoundedIcon from '@mui/icons-material/InfoRounded';
import {
  ExpandLess,
  ExpandMore,
  TapAndPlay,
  CellTower,
  Wifi,
} from '@mui/icons-material';
import { useState } from 'react';
import { Collapse, Divider } from '@mui/material';
import { useLocation, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

// TODO this should be built dynamically based on data in Firebase
const devices = ['RPI-1', 'RPI-2', 'RPI-3'];

const secondaryListItems = [
  { key: 'common.settings', icon: <SettingsRoundedIcon /> },
  { key: 'common.about', icon: <InfoRoundedIcon /> },
];

export default function MenuContent({ collapsed = false }) {
  const [openDevices, setOpenDevices] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const { t } = useTranslation();
  const iconSx = collapsed
    ? {
        minWidth: 'auto',
        mr: 0,
        display: 'flex',
        justifyContent: 'center',
        '& .MuiSvgIcon-root': {
          fontSize: '1.5rem',
        },
      }
    : undefined;

  return (
    <Stack sx={{ flexGrow: 1, p: 1, justifyContent: 'space-between' }}>
      <List dense>
        {/* Home */}
        <ListItem disablePadding>
          <ListItemButton
            selected={location.pathname === '/home'}
            onClick={() => navigate('/home')}
            sx={collapsed ? { justifyContent: 'center' } : undefined}
          >
            <ListItemIcon sx={iconSx}>
              <HomeRoundedIcon />
            </ListItemIcon>
            {!collapsed && <ListItemText primary={t('common.home')} />}
          </ListItemButton>
        </ListItem>

        {/* SSIDs */}
        <ListItem disablePadding>
          <ListItemButton
            selected={location.pathname === '/ssids'}
            onClick={() => navigate('/ssids')}
            sx={collapsed ? { justifyContent: 'center' } : undefined}
          >
            <ListItemIcon sx={iconSx}>
              <Wifi />
            </ListItemIcon>
            {!collapsed && <ListItemText primary={t('common.ssids')} />}
          </ListItemButton>
        </ListItem>

        {/* Devices (parent) */}
        <ListItem disablePadding>
          <ListItemButton
            onClick={() => setOpenDevices(!openDevices)}
            sx={collapsed ? { justifyContent: 'center' } : undefined}
          >
            <ListItemIcon sx={iconSx}>
              <CellTower />
            </ListItemIcon>
            {!collapsed && <ListItemText primary={t('common.devices')} />}
            {!collapsed && (openDevices ? <ExpandLess /> : <ExpandMore />)}
          </ListItemButton>
        </ListItem>

        {/* Devices (children) */}
        <Collapse in={!collapsed && openDevices} timeout="auto" unmountOnExit>
          <List component="div" dense disablePadding>
            {devices.map((device) => (
              <ListItem key={device} disablePadding sx={{ pl: 4 }}>
                <ListItemButton
                  selected={location.pathname === `/device/${device}`}
                  onClick={() => navigate(`/device/${device}`)}
                >
                  <ListItemIcon sx={iconSx}>
                    <TapAndPlay />
                  </ListItemIcon>
                  <ListItemText primary={device} />
                </ListItemButton>
              </ListItem>
            ))}
          </List>
        </Collapse>
      </List>
      <List dense>
        <Divider />
        {secondaryListItems.map((item, index) => (
          <ListItem key={index} disablePadding sx={{ display: 'block' }}>
            <ListItemButton
              sx={collapsed ? { justifyContent: 'center' } : undefined}
            >
              <ListItemIcon sx={iconSx}>{item.icon}</ListItemIcon>
              {!collapsed && <ListItemText primary={t(item.key)} />}
            </ListItemButton>
          </ListItem>
        ))}
      </List>
    </Stack>
  );
}
