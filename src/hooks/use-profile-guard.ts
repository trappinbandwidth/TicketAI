import { useCallback, useRef, useState } from 'react';
import { useAtom } from 'jotai';
import type { ProfileCompletionContext } from 'src/components/shared/CompleteProfileModal';
import { driverProfile } from 'src/store';

/**
 * Hook that guards actions behind a profile-completeness check.
 *
 * Usage:
 * ```tsx
 * const { guardAction, profileDialogProps } = useProfileGuard();
 *
 * When `driverData.incompleteProfile` is truthy, the action is blocked
 * and the dialog props will open the warning dialog instead.
 */
export function useProfileGuard() {
    const [driverData] = useAtom(driverProfile);
    const [showDialog, setShowDialog] = useState(false);
    const [showCompletionModal, setShowCompletionModal] = useState(false);
    const [actionContext, setActionContext] = useState<ProfileCompletionContext>('general');
    const pendingActionRef = useRef<(() => void) | null>(null);
    const hasIncompleteProfile = Boolean(driverData?.incompleteProfile);

    const guardAction = useCallback(
        (action: () => void, context: ProfileCompletionContext = 'general') => () => {
            if (hasIncompleteProfile) {
                pendingActionRef.current = action;
                setActionContext(context);
                setShowDialog(true);
            } else {
                action();
            }
        },
        [hasIncompleteProfile]
    );

    const handleClose = useCallback(() => {
        pendingActionRef.current = null;
        setShowDialog(false);
    }, []);

    const openProfileCompletion = useCallback((context: ProfileCompletionContext = 'general') => {
        setActionContext(context);
        setShowDialog(false);
        setShowCompletionModal(true);
    }, []);

    const handleCloseCompletion = useCallback(() => {
        pendingActionRef.current = null;
        setShowCompletionModal(false);
    }, []);

    const handleProfileCompleted = useCallback(() => {
        setShowDialog(false);
        setShowCompletionModal(false);

        const pendingAction = pendingActionRef.current;
        pendingActionRef.current = null;
        pendingAction?.();
    }, []);

    return {
        hasIncompleteProfile,
        guardAction,
        openProfileCompletion,
        profileDialogProps: {
            open: showDialog,
            onClose: handleClose,
            onCompleteProfile: () => openProfileCompletion(actionContext),
        },
        completeProfileModalProps: {
            open: showCompletionModal,
            onClose: handleCloseCompletion,
            onCompleted: handleProfileCompleted,
            actionContext,
            skipExplanation: actionContext === 'general',
        },
    };
}
