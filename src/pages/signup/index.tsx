import NewMemberSignupFlow from './components/NewMemberSignupFlow';

/**
 * SignUp Page - Entry point for new users
 * Displays options to either sign up for membership or submit a ticket as guest
 * Matches Figma design pixel-perfect with Rig Resolve branding
 */
export default function SignUpPage() {
  return <NewMemberSignupFlow />;
}

/*
Legacy signup route implementation kept per request.

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import NewUserWelcome from './components/NewUserWelcome';
import SignupFlow from './components/SignupFlow';
import GuestTicketSubmission from './components/GuestTicketSubmission';

export default function SignUpPage() {
  const navigate = useNavigate();
  const [showNewUserWelcome, setShowNewUserWelcome] = useState(true);
  const [showSignupFlow, setShowSignupFlow] = useState(false);
  const [showGuestTicketSubmission, setShowGuestTicketSubmission] = useState(false);

  const handleSelectSignup = () => {
    setShowNewUserWelcome(false);
    setShowSignupFlow(true);
  };

  const handleSelectTicketSubmission = () => {
    setShowNewUserWelcome(false);
    setShowGuestTicketSubmission(true);
  };

  const handleCloseWelcome = () => {
    navigate('/sign-in');
  };

  const handleSignupComplete = (plan: 'silver' | 'gold' | 'platinum') => {
    handleCloseWelcome();
  };

  const handleGuestSignupInstead = () => {
    setShowGuestTicketSubmission(false);
    setShowSignupFlow(true);
  };

  const handleCloseSignupFlow = () => {
    setShowSignupFlow(false);
    setShowNewUserWelcome(true);
  };

  const handleCloseGuestTicket = () => {
    setShowGuestTicketSubmission(false);
    setShowNewUserWelcome(true);
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-brand-auth-soft px-2 py-6">
      {showNewUserWelcome && (
        <NewUserWelcome
          isOpen={showNewUserWelcome}
          onClose={handleCloseWelcome}
          onSelectSignup={handleSelectSignup}
          onSelectTicketSubmission={handleSelectTicketSubmission}
        />
      )}

      {showSignupFlow && (
        <SignupFlow
          isOpen={showSignupFlow}
          onClose={handleCloseSignupFlow}
          onSignupComplete={handleSignupComplete}
        />
      )}

      {showGuestTicketSubmission && (
        <GuestTicketSubmission
          isOpen={showGuestTicketSubmission}
          onClose={handleCloseGuestTicket}
          onSignupInstead={handleGuestSignupInstead}
        />
      )}
    </div>
  );
}
*/
