import { FormProvider as Form } from 'react-hook-form';
import React from 'react';

interface FormProviderProps {
  children: React.ReactNode;
  onSubmit: () => void;
  methods: any; // Update this type to match the actual type of 'methods'
}

const FormProvider: React.FC<FormProviderProps> = ({ children, onSubmit, methods }) => {
  return (
    <Form {...methods}>
      <form onSubmit={onSubmit}>{children}</form>
    </Form>
  );
};

export default FormProvider;
