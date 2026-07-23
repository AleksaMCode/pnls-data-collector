import * as React from 'react';
import LanguageRoundedIcon from '@mui/icons-material/LanguageRounded';
import IconButton from '@mui/material/IconButton';
import ListItemText from '@mui/material/ListItemText';
import Menu from '@mui/material/Menu';
import MenuItem from '@mui/material/MenuItem';
import { useTranslation } from 'react-i18next';

const LANGUAGES = [
  { code: 'en', key: 'language.english' },
  { code: 'fr', key: 'language.french' },
  { code: 'de', key: 'language.german' },
];

export default function LanguageIconDropdown(props) {
  const { t, i18n } = useTranslation();
  const [anchorEl, setAnchorEl] = React.useState(null);
  const open = Boolean(anchorEl);
  const currentLang = i18n.resolvedLanguage || i18n.language || 'en';

  const handleClick = (event) => {
    setAnchorEl(event.currentTarget);
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  const handleLanguage = (languageCode) => () => {
    i18n.changeLanguage(languageCode);
    handleClose();
  };

  return (
    <>
      <IconButton
        onClick={handleClick}
        disableRipple
        size="small"
        aria-controls={open ? 'language-menu' : undefined}
        aria-haspopup="true"
        aria-expanded={open ? 'true' : undefined}
        {...props}
      >
        <LanguageRoundedIcon />
      </IconButton>
      <Menu
        anchorEl={anchorEl}
        id="language-menu"
        open={open}
        onClose={handleClose}
        onClick={handleClose}
        transformOrigin={{ horizontal: 'right', vertical: 'top' }}
        anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
      >
        {LANGUAGES.map((language) => (
          <MenuItem
            key={language.code}
            selected={currentLang.startsWith(language.code)}
            onClick={handleLanguage(language.code)}
          >
            <ListItemText>{t(language.key)}</ListItemText>
          </MenuItem>
        ))}
      </Menu>
    </>
  );
}
