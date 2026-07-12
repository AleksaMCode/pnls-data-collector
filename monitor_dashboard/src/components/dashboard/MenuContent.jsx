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

// TODO this should be built dynamically based on data in Firebase
const devices = ['RPI-1', 'RPI-2', 'RPI-3'];

const secondaryListItems = [
  { text: 'Settings', icon: <SettingsRoundedIcon /> },
  { text: 'About', icon: <InfoRoundedIcon /> },
];

export default function MenuContent() {
  const [openDevices, setOpenDevices] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <Stack sx={{ flexGrow: 1, p: 1, justifyContent: 'space-between' }}>
      <List dense>
        {/* Home */}
        <ListItem disablePadding>
          <ListItemButton
            selected={location.pathname === '/home'}
            onClick={() => navigate('/home')}
          >
            <ListItemIcon>
              <HomeRoundedIcon />
            </ListItemIcon>
            <ListItemText primary="Home" />
          </ListItemButton>
        </ListItem>

        {/* SSIDs */}
        <ListItem disablePadding>
          <ListItemButton
            selected={location.pathname === '/ssids'}
            onClick={() => navigate('/ssids')}
          >
            <ListItemIcon>
              <Wifi />
            </ListItemIcon>
            <ListItemText primary="SSIDs" />
          </ListItemButton>
        </ListItem>

        {/* Devices (parent) */}
        <ListItem disablePadding>
          <ListItemButton onClick={() => setOpenDevices(!openDevices)}>
            <ListItemIcon>
              <CellTower />
            </ListItemIcon>
            <ListItemText primary="Devices (live view)" />
            {openDevices ? <ExpandLess /> : <ExpandMore />}
          </ListItemButton>
        </ListItem>

        {/* Devices (children) */}
        <Collapse in={openDevices} timeout="auto" unmountOnExit>
          <List component="div" dense disablePadding>
            {devices.map((device) => (
              <ListItem key={device} disablePadding sx={{ pl: 4 }}>
                <ListItemButton
                  selected={location.pathname === `/device/${device}`}
                  onClick={() => navigate(`/device/${device}`)}
                >
                  <ListItemIcon>
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
            <ListItemButton>
              <ListItemIcon>{item.icon}</ListItemIcon>
              <ListItemText primary={item.text} />
            </ListItemButton>
          </ListItem>
        ))}
      </List>
    </Stack>
  );
}
