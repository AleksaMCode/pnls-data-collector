import { Box, Avatar, Typography, Stack } from '@mui/material';
import DevicesRoundedIcon from '@mui/icons-material/DevicesRounded';
import { styled } from '@mui/material/styles';

const BubbleItemContainer = styled(Box)(({ theme }) => ({
  display: 'flex',
  alignItems: 'center',
  gap: 12,
  padding: '8px 12px',
  borderRadius: 24,
  backgroundColor: (theme.vars || theme).palette.background.paper,
  border: `1px solid ${(theme.vars || theme).palette.divider}`,
  cursor: 'pointer',
  transition: 'background-color 0.2s',
  '&:hover': {
    backgroundColor: (theme.vars || theme).palette.background.paper,
  },
}));

export default function PnlsCard({ primary, secondary, icon, color }) {
  return (
    <BubbleItemContainer>
      <Avatar
        sx={{
          bgcolor: color || 'primary.main',
          width: 60,
          height: 60,
          fontSize: '1rem',
        }}
      >
        {icon || <DevicesRoundedIcon fontSize="small" />}
      </Avatar>
      <Stack spacing={0.2}>
        <Typography variant="body2" fontWeight={500} color="text.secondary">
          {primary}
        </Typography>
        {secondary && (
          <Typography variant="caption" color="text.secondary">
            {secondary}
          </Typography>
        )}
      </Stack>
    </BubbleItemContainer>
  );
}
