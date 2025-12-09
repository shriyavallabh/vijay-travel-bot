import { useEffect, useState, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Title, useNotify } from 'react-admin';
import {
  Box,
  Paper,
  List,
  ListItem,
  ListItemText,
  ListItemAvatar,
  Avatar,
  Typography,
  TextField,
  IconButton,
  Badge,
  Divider,
  Chip,
  CircularProgress,
  Switch,
  FormControlLabel,
  Tooltip,
} from '@mui/material';
import SendIcon from '@mui/icons-material/Send';
import PersonIcon from '@mui/icons-material/Person';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import AdminPanelSettingsIcon from '@mui/icons-material/AdminPanelSettings';
import RefreshIcon from '@mui/icons-material/Refresh';
import WhatsAppIcon from '@mui/icons-material/WhatsApp';
import { chatApi } from '../providers/dataProvider';
import { format } from 'date-fns';

interface User {
  id: number;
  phone: string;
  name: string | null;
  bot_paused: boolean;
  trip_status: string;
  last_message_at: string | null;
}

interface Message {
  id: number;
  user_id: number;
  content: string;
  sender_type: 'user' | 'bot' | 'admin';
  timestamp: string;
  is_read: boolean;
}

interface Conversation {
  user: User;
  latest_message: Message | null;
  unread_count: number;
}

// Chat Bubble Component
const ChatBubble = ({ message }: { message: Message }) => {
  const isUser = message.sender_type === 'user';
  const isAdmin = message.sender_type === 'admin';
  const isBot = message.sender_type === 'bot';

  const getBubbleColor = () => {
    if (isUser) return '#e3f2fd';
    if (isAdmin) return '#fff3e0';
    return '#e8f5e9';
  };

  const getIcon = () => {
    if (isUser) return <PersonIcon />;
    if (isAdmin) return <AdminPanelSettingsIcon />;
    return <SmartToyIcon />;
  };

  const getLabel = () => {
    if (isUser) return 'Customer';
    if (isAdmin) return 'Admin';
    return 'Bot';
  };

  return (
    <Box
      sx={{
        display: 'flex',
        justifyContent: isUser ? 'flex-start' : 'flex-end',
        mb: 2,
        px: 2,
      }}
    >
      <Box
        sx={{
          maxWidth: '70%',
          display: 'flex',
          flexDirection: isUser ? 'row' : 'row-reverse',
          alignItems: 'flex-end',
          gap: 1,
        }}
      >
        <Avatar
          sx={{
            width: 32,
            height: 32,
            bgcolor: isUser ? '#2196f3' : isAdmin ? '#ff9800' : '#4caf50',
          }}
        >
          {getIcon()}
        </Avatar>
        <Paper
          elevation={1}
          sx={{
            p: 2,
            backgroundColor: getBubbleColor(),
            borderRadius: 2,
            borderBottomLeftRadius: isUser ? 0 : 2,
            borderBottomRightRadius: isUser ? 2 : 0,
          }}
        >
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
            {getLabel()}
          </Typography>
          <Typography variant="body1" sx={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
            {message.content}
          </Typography>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1, textAlign: 'right' }}>
            {format(new Date(message.timestamp), 'MMM d, HH:mm')}
          </Typography>
        </Paper>
      </Box>
    </Box>
  );
};

// Conversation List Item
const ConversationItem = ({
  conversation,
  selected,
  onClick,
}: {
  conversation: Conversation;
  selected: boolean;
  onClick: () => void;
}) => (
  <ListItem
    button
    selected={selected}
    onClick={onClick}
    sx={{
      borderLeft: selected ? '4px solid #1976d2' : '4px solid transparent',
      '&:hover': { backgroundColor: '#f5f5f5' },
    }}
  >
    <ListItemAvatar>
      <Badge badgeContent={conversation.unread_count} color="error">
        <Avatar sx={{ bgcolor: conversation.user.bot_paused ? '#ff9800' : '#4caf50' }}>
          <PersonIcon />
        </Avatar>
      </Badge>
    </ListItemAvatar>
    <ListItemText
      primary={
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography variant="subtitle2">{conversation.user.name || conversation.user.phone}</Typography>
          {conversation.user.bot_paused && (
            <Chip label="Paused" size="small" color="warning" sx={{ height: 20 }} />
          )}
        </Box>
      }
      secondary={
        <Typography variant="body2" color="text.secondary" noWrap sx={{ maxWidth: 200 }}>
          {conversation.latest_message?.content || 'No messages'}
        </Typography>
      }
    />
    {conversation.latest_message && (
      <Typography variant="caption" color="text.secondary">
        {format(new Date(conversation.latest_message.timestamp), 'HH:mm')}
      </Typography>
    )}
  </ListItem>
);

// Main Chat Interface Component
export const ChatInterface = () => {
  const { userId } = useParams<{ userId: string }>();
  const navigate = useNavigate();
  const notify = useNotify();

  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [newMessage, setNewMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [sendViaWhatsApp, setSendViaWhatsApp] = useState(true);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Fetch conversations
  const fetchConversations = async () => {
    try {
      const data = await chatApi.getConversations(1, 50);
      setConversations(data.data);
    } catch (error) {
      notify('Failed to load conversations', { type: 'error' });
    }
  };

  // Fetch messages for selected user
  const fetchMessages = async (uid: number) => {
    try {
      const data = await chatApi.getMessages(uid, 1, 100);
      setSelectedUser(data.user);
      setMessages(data.messages);
      // Mark as read
      await chatApi.markAsRead(uid);
      fetchConversations(); // Refresh unread counts
    } catch (error) {
      notify('Failed to load messages', { type: 'error' });
    }
  };

  // Send message
  const handleSend = async () => {
    if (!newMessage.trim() || !selectedUser) return;

    setSending(true);
    try {
      await chatApi.sendMessage(selectedUser.id, newMessage, sendViaWhatsApp);
      setNewMessage('');
      // Refresh messages
      await fetchMessages(selectedUser.id);
      notify('Message sent', { type: 'success' });
    } catch (error) {
      notify('Failed to send message', { type: 'error' });
    } finally {
      setSending(false);
    }
  };

  // Toggle bot status
  const handleToggleBot = async () => {
    if (!selectedUser) return;
    try {
      const result = await chatApi.toggleBotStatus(selectedUser.id);
      notify(result.message, { type: 'success' });
      fetchMessages(selectedUser.id);
      fetchConversations();
    } catch (error) {
      notify('Failed to toggle bot status', { type: 'error' });
    }
  };

  // Scroll to bottom of messages
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  // Initial load
  useEffect(() => {
    const init = async () => {
      setLoading(true);
      await fetchConversations();
      if (userId) {
        await fetchMessages(parseInt(userId));
      }
      setLoading(false);
    };
    init();
  }, [userId]);

  // Scroll when messages change
  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Auto-refresh every 10 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      fetchConversations();
      if (selectedUser) {
        fetchMessages(selectedUser.id);
      }
    }, 10000);
    return () => clearInterval(interval);
  }, [selectedUser]);

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '80vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ height: 'calc(100vh - 64px)', display: 'flex', flexDirection: 'column' }}>
      <Title title="Chat Interface" />

      <Box sx={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        {/* Left: Conversation List */}
        <Paper
          sx={{
            width: 350,
            borderRight: '1px solid #e0e0e0',
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
          }}
        >
          <Box sx={{ p: 2, borderBottom: '1px solid #e0e0e0', display: 'flex', alignItems: 'center', gap: 1 }}>
            <Typography variant="h6" sx={{ flex: 1 }}>
              Conversations
            </Typography>
            <IconButton size="small" onClick={fetchConversations}>
              <RefreshIcon />
            </IconButton>
          </Box>
          <List sx={{ flex: 1, overflow: 'auto', p: 0 }}>
            {conversations.length === 0 ? (
              <Box sx={{ p: 3, textAlign: 'center' }}>
                <Typography color="text.secondary">No conversations yet</Typography>
              </Box>
            ) : (
              conversations.map((conv) => (
                <ConversationItem
                  key={conv.user.id}
                  conversation={conv}
                  selected={selectedUser?.id === conv.user.id}
                  onClick={() => {
                    navigate(`/chat/${conv.user.id}`);
                    fetchMessages(conv.user.id);
                  }}
                />
              ))
            )}
          </List>
        </Paper>

        {/* Right: Chat Window */}
        <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          {selectedUser ? (
            <>
              {/* Chat Header */}
              <Paper
                sx={{
                  p: 2,
                  borderBottom: '1px solid #e0e0e0',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 2,
                }}
              >
                <Avatar sx={{ bgcolor: selectedUser.bot_paused ? '#ff9800' : '#4caf50' }}>
                  <PersonIcon />
                </Avatar>
                <Box sx={{ flex: 1 }}>
                  <Typography variant="h6">{selectedUser.name || selectedUser.phone}</Typography>
                  <Typography variant="body2" color="text.secondary">
                    {selectedUser.phone} | {selectedUser.trip_status}
                  </Typography>
                </Box>
                <FormControlLabel
                  control={
                    <Switch
                      checked={selectedUser.bot_paused}
                      onChange={handleToggleBot}
                      color="warning"
                    />
                  }
                  label={selectedUser.bot_paused ? 'Bot Paused' : 'Bot Active'}
                />
              </Paper>

              {/* Messages */}
              <Box sx={{ flex: 1, overflow: 'auto', py: 2, backgroundColor: '#fafafa' }}>
                {messages.length === 0 ? (
                  <Box sx={{ textAlign: 'center', py: 4 }}>
                    <Typography color="text.secondary">No messages yet</Typography>
                  </Box>
                ) : (
                  messages.map((msg) => <ChatBubble key={msg.id} message={msg} />)
                )}
                <div ref={messagesEndRef} />
              </Box>

              {/* Message Input */}
              <Paper sx={{ p: 2, borderTop: '1px solid #e0e0e0' }}>
                <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', mb: 1 }}>
                  <FormControlLabel
                    control={
                      <Switch
                        checked={sendViaWhatsApp}
                        onChange={(e) => setSendViaWhatsApp(e.target.checked)}
                        size="small"
                      />
                    }
                    label={
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                        <WhatsAppIcon fontSize="small" color={sendViaWhatsApp ? 'success' : 'disabled'} />
                        <Typography variant="caption">Send via WhatsApp</Typography>
                      </Box>
                    }
                  />
                </Box>
                <Box sx={{ display: 'flex', gap: 1 }}>
                  <TextField
                    fullWidth
                    multiline
                    maxRows={4}
                    placeholder="Type your message..."
                    value={newMessage}
                    onChange={(e) => setNewMessage(e.target.value)}
                    onKeyPress={(e) => {
                      if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        handleSend();
                      }
                    }}
                    disabled={sending}
                    size="small"
                  />
                  <Tooltip title="Send Message">
                    <IconButton color="primary" onClick={handleSend} disabled={sending || !newMessage.trim()}>
                      {sending ? <CircularProgress size={24} /> : <SendIcon />}
                    </IconButton>
                  </Tooltip>
                </Box>
              </Paper>
            </>
          ) : (
            <Box
              sx={{
                flex: 1,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                backgroundColor: '#fafafa',
              }}
            >
              <Typography color="text.secondary">Select a conversation to start chatting</Typography>
            </Box>
          )}
        </Box>
      </Box>
    </Box>
  );
};
