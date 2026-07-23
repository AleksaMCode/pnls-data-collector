import { styled } from '@mui/material/styles';
import Typography from '@mui/material/Typography';
import Breadcrumbs, { breadcrumbsClasses } from '@mui/material/Breadcrumbs';
import NavigateNextRoundedIcon from '@mui/icons-material/NavigateNextRounded';
import { Link, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

const StyledBreadcrumbs = styled(Breadcrumbs)(({ theme }) => ({
  margin: theme.spacing(1, 0),
  [`& .${breadcrumbsClasses.separator}`]: {
    color: (theme.vars || theme).palette.action.disabled,
    margin: 1,
  },
  [`& .${breadcrumbsClasses.ol}`]: {
    alignItems: 'center',
  },
}));

export default function NavbarBreadcrumbs() {
  const location = useLocation();
  const { t } = useTranslation();

  // Split path into parts
  const pathnames = location.pathname.split('/').filter(Boolean);
  return (
    <StyledBreadcrumbs
      aria-label="breadcrumb"
      separator={<NavigateNextRoundedIcon fontSize="small" />}
    >
      {/* Root */}
      <Typography
        component={Link}
        to="/home"
        variant="body1"
        sx={{ textDecoration: 'none', color: 'text.secondary' }}
      >
        {t('common.dashboard')}
      </Typography>

      {pathnames.map((value, index) => {
        const to = `/${pathnames.slice(0, index + 1).join('/')}`;
        const isLast = index === pathnames.length - 1;

        const label =
          value === 'home'
            ? t('breadcrumbs.home')
            : value === 'device'
              ? t('breadcrumbs.device')
              : value;

        return isLast ? (
          <Typography
            key={to}
            variant="body1"
            sx={{ color: 'text.primary', fontWeight: 600 }}
          >
            {label}
          </Typography>
        ) : (
          <Typography
            key={to}
            component={Link}
            to={to}
            variant="body1"
            sx={{ textDecoration: 'none', color: 'text.secondary' }}
          >
            {label}
          </Typography>
        );
      })}
    </StyledBreadcrumbs>
  );
}
